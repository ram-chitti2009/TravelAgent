import os
import requests
import serpapi


INTERCITY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_intercity_travel",
        "description": (
            "Find travel options between two cities within the same country or region — "
            "including driving (with gas cost estimate), intercity buses (Greyhound, FlixBus), "
            "and regional trains (Amtrak). Best for trips under 1000 miles where flying may not "
            "make sense. Use this instead of search_flights for regional/domestic city-to-city travel."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin_city": {
                    "type": "string",
                    "description": "Departure city, e.g. 'Dallas, TX'",
                },
                "destination_city": {
                    "type": "string",
                    "description": "Destination city, e.g. 'Oklahoma City, OK'",
                },
                "travel_date": {
                    "type": "string",
                    "description": "Travel date in YYYY-MM-DD format (used for bus/train schedule lookup)",
                },
                "passengers": {
                    "type": "integer",
                    "description": "Number of passengers (affects gas cost split estimate)",
                    "default": 1,
                },
            },
            "required": ["origin_city", "destination_city"],
        },
    },
}

# Average fuel efficiency (mpg) and gas price (USD/gallon)
AVG_MPG = 28.0
AVG_GAS_PRICE_USD = 3.40  # approximate US national average


def _driving_option(origin: str, destination: str, passengers: int) -> dict | None:
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")

    dist_km = None
    duration_minutes = None

    if google_key:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": origin,
                    "destinations": destination,
                    "mode": "driving",
                    "units": "imperial",
                    "key": google_key,
                },
                timeout=10,
            )
            data = resp.json()
            element = data["rows"][0]["elements"][0]
            if element["status"] == "OK":
                dist_km = element["distance"]["value"] / 1000
                duration_minutes = element["duration"]["value"] // 60
        except Exception:
            pass

    # OSM fallback
    if dist_km is None:
        try:
            def _geocode(place: str):
                r = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": place, "format": "json", "limit": 1},
                    headers={"User-Agent": "TravelAgent/1.0"},
                    timeout=10,
                )
                d = r.json()
                if d:
                    return float(d[0]["lat"]), float(d[0]["lon"])
                return None

            o = _geocode(origin)
            d = _geocode(destination)
            if o and d:
                url = f"http://router.project-osrm.org/route/v1/driving/{o[1]},{o[0]};{d[1]},{d[0]}"
                r2 = requests.get(url, params={"overview": "false"}, timeout=10)
                route = r2.json()
                if route.get("code") == "Ok":
                    dist_km = route["routes"][0]["distance"] / 1000
                    duration_minutes = route["routes"][0]["duration"] // 60
        except Exception:
            pass

    if dist_km is None:
        return None

    dist_miles = dist_km * 0.621371
    gallons = dist_miles / AVG_MPG
    total_gas = round(gallons * AVG_GAS_PRICE_USD, 2)
    per_person = round(total_gas / max(passengers, 1), 2)

    h, m = divmod(duration_minutes, 60)
    drive_summary = f"{h}h {m}min" if h else f"{m}min"

    stops_note = ""
    if dist_miles > 300:
        stops_note = f" — consider 1–2 rest stops on this {round(dist_miles)} mi drive"

    return {
        "type": "driving",
        "provider": "Self-drive",
        "duration_minutes": duration_minutes,
        "distance_miles": round(dist_miles, 1),
        "distance_km": round(dist_km, 1),
        "total_gas_cost_usd": total_gas,
        "gas_cost_per_person_usd": per_person,
        "cost_estimate": f"~${total_gas:.0f} gas total (${per_person:.0f}/person)",
        "description": (
            f"{round(dist_miles)} miles · {drive_summary} drive{stops_note}. "
            f"Gas estimate based on {AVG_MPG}mpg avg at ${AVG_GAS_PRICE_USD}/gal."
        ),
        "booking_link": (
            f"https://www.google.com/maps/dir/{origin.replace(' ', '+')}/{destination.replace(' ', '+')}"
        ),
    }


def _bus_options(origin: str, destination: str, travel_date: str = None) -> list[dict]:
    options = []
    try:
        query = f"bus from {origin} to {destination}"
        if travel_date:
            query += f" {travel_date}"

        params = {
            "engine": "google",
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }
        results = serpapi.search(params)

        # Pull organic snippets that mention Greyhound / FlixBus / bus
        bus_providers = ["greyhound", "flixbus", "megabus", "peter pan", "trailways"]
        for result in results.get("organic_results", [])[:8]:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            provider = next((p.title() for p in bus_providers if p in title or p in link.lower()), None)
            if provider:
                options.append({
                    "type": "bus",
                    "provider": provider,
                    "duration_minutes": None,
                    "cost_estimate": "See website for fares",
                    "description": snippet[:200] if snippet else f"{provider} intercity bus service.",
                    "booking_link": link,
                })
            if len(options) >= 2:
                break
    except Exception:
        pass
    return options


def _train_options(origin: str, destination: str) -> list[dict]:
    options = []
    try:
        query = f"Amtrak train from {origin} to {destination}"
        params = {
            "engine": "google",
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }
        results = serpapi.search(params)

        for result in results.get("organic_results", [])[:5]:
            link = result.get("link", "")
            if "amtrak.com" in link:
                options.append({
                    "type": "train",
                    "provider": "Amtrak",
                    "duration_minutes": None,
                    "cost_estimate": "See Amtrak for fares",
                    "description": result.get("snippet", "Amtrak intercity rail service.")[:200],
                    "booking_link": link,
                })
                break

        # Always surface Amtrak search link as fallback
        if not options:
            orig_clean = origin.split(",")[0].strip()
            dest_clean = destination.split(",")[0].strip()
            options.append({
                "type": "train",
                "provider": "Amtrak",
                "duration_minutes": None,
                "cost_estimate": "Check Amtrak.com",
                "description": f"Search Amtrak routes from {orig_clean} to {dest_clean}.",
                "booking_link": f"https://www.amtrak.com/tickets/departure.html",
            })
    except Exception:
        pass
    return options


def search_intercity_travel(
    origin_city: str,
    destination_city: str,
    travel_date: str = None,
    passengers: int = 1,
) -> dict:
    options = []

    drive = _driving_option(origin_city, destination_city, passengers)
    if drive:
        options.append(drive)

    buses = _bus_options(origin_city, destination_city, travel_date)
    options.extend(buses)

    trains = _train_options(origin_city, destination_city)
    options.extend(trains)

    if not options:
        return {
            "error": "Could not retrieve travel options. Check city names and try again.",
            "options": [],
        }

    return {
        "origin": origin_city,
        "destination": destination_city,
        "options": options,
    }
