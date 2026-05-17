import os
import requests


MAPS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_distance",
        "description": (
            "Calculate distance and travel time between two locations. "
            "Useful for planning how far attractions or hotels are from each other."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Starting location, e.g. 'Eiffel Tower, Paris' or hotel name",
                },
                "destination": {
                    "type": "string",
                    "description": "Ending location, e.g. 'Louvre Museum, Paris'",
                },
                "mode": {
                    "type": "string",
                    "enum": ["driving", "walking", "transit", "bicycling"],
                    "description": "Mode of transport for the route calculation",
                    "default": "transit",
                },
            },
            "required": ["origin", "destination"],
        },
    },
}


def _geocode_osm(place: str) -> tuple[float, float] | None:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": "TravelAgent/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def _osrm_route(lat1: float, lon1: float, lat2: float, lon2: float, mode: str) -> dict | None:
    # OSRM supports: driving, walking (foot), cycling
    profile_map = {"driving": "driving", "walking": "foot", "bicycling": "cycling", "transit": "driving"}
    profile = profile_map.get(mode, "driving")
    try:
        url = f"http://router.project-osrm.org/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}"
        resp = requests.get(url, params={"overview": "false"}, timeout=10)
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            return {
                "distance_km": round(route["distance"] / 1000, 2),
                "duration_minutes": round(route["duration"] / 60),
            }
    except Exception:
        pass
    return None


def get_distance(
    origin: str,
    destination: str,
    mode: str = "transit",
) -> dict:
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")

    # Try Google Maps Distance Matrix first
    if google_key:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": origin,
                    "destinations": destination,
                    "mode": mode,
                    "units": "metric",
                    "key": google_key,
                },
                timeout=10,
            )
            data = resp.json()
            element = data["rows"][0]["elements"][0]
            if element["status"] == "OK":
                dist_km = round(element["distance"]["value"] / 1000, 2)
                dur_min = round(element["duration"]["value"] / 60)
                return {
                    "origin": origin,
                    "destination": destination,
                    "distance_km": dist_km,
                    "duration_minutes": dur_min,
                    "mode": mode,
                    "summary": f"{dist_km} km, about {dur_min} min by {mode}",
                }
        except Exception:
            pass

    # Fallback: OSM Nominatim + OSRM
    origin_coords = _geocode_osm(origin)
    dest_coords = _geocode_osm(destination)

    if not origin_coords or not dest_coords:
        return {"error": "Could not geocode one or both locations", "origin": origin, "destination": destination}

    route = _osrm_route(*origin_coords, *dest_coords, mode)
    if not route:
        return {"error": "Could not calculate route", "origin": origin, "destination": destination}

    note = " (transit estimated as driving)" if mode == "transit" else ""
    return {
        "origin": origin,
        "destination": destination,
        "distance_km": route["distance_km"],
        "duration_minutes": route["duration_minutes"],
        "mode": mode,
        "summary": f"{route['distance_km']} km, about {route['duration_minutes']} min by {mode}{note}",
    }
