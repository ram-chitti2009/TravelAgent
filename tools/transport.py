import os
import requests
from .maps import get_distance


TRANSPORT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_local_transport",
        "description": (
            "Find short-distance local transport options between two points in a city, "
            "including metro, bus, train, and rideshare cost estimates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Starting point within the city, e.g. 'Gare du Nord, Paris'",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination within the city, e.g. 'Hotel Le Marais, Paris'",
                },
                "city": {
                    "type": "string",
                    "description": "City context for transport network, e.g. 'Paris'",
                },
                "transport_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific transport types to include, e.g. ['metro', 'taxi']. Omit for all options.",
                },
            },
            "required": ["origin", "destination", "city"],
        },
    },
}

# Approximate per-km rideshare rates (USD) by city tier
_RIDESHARE_RATES = {
    "default": {"base": 2.5, "per_km": 1.2},
    "new york": {"base": 3.0, "per_km": 1.8},
    "london": {"base": 3.5, "per_km": 2.0},
    "tokyo": {"base": 4.0, "per_km": 2.5},
    "paris": {"base": 3.0, "per_km": 1.5},
    "dubai": {"base": 2.0, "per_km": 0.8},
    "mumbai": {"base": 1.0, "per_km": 0.4},
}

# Flat metro/bus fares by city (USD approximate)
_TRANSIT_FARES = {
    "default": {"metro": "$1.50–$3.00", "bus": "$1.00–$2.50"},
    "new york": {"metro": "$2.90", "bus": "$2.90"},
    "london": {"metro": "£2.70–£6.70", "bus": "£1.75"},
    "paris": {"metro": "€1.90", "bus": "€1.90"},
    "tokyo": {"metro": "¥170–¥320", "bus": "¥210"},
    "dubai": {"metro": "AED 3–8", "bus": "AED 3"},
    "sydney": {"metro": "AUD 2–5", "bus": "AUD 2–4"},
}


def _get_rates(city: str) -> tuple[dict, dict]:
    city_lower = city.lower()
    ride = _RIDESHARE_RATES.get(city_lower, _RIDESHARE_RATES["default"])
    transit = _TRANSIT_FARES.get(city_lower, _TRANSIT_FARES["default"])
    return ride, transit


def get_local_transport(
    origin: str,
    destination: str,
    city: str,
    transport_types: list = None,
) -> dict:
    try:
        routes = []
        ride_rates, transit_fares = _get_rates(city)

        # Get distance via maps tool
        dist_data = get_distance(origin, destination, mode="driving")
        dist_km = dist_data.get("distance_km", 5)
        drive_minutes = dist_data.get("duration_minutes", 15)

        transit_data = get_distance(origin, destination, mode="walking")
        walk_minutes = transit_data.get("duration_minutes", 0)

        want = set(transport_types) if transport_types else {"metro", "bus", "taxi", "rideshare", "walking"}

        if "walking" in want and walk_minutes <= 30:
            routes.append({
                "type": "walking",
                "provider": "On foot",
                "duration_minutes": walk_minutes,
                "cost_estimate": "Free",
                "description": f"Walk {dist_km} km, approximately {walk_minutes} minutes.",
                "booking_link": None,
            })

        if "metro" in want or "bus" in want:
            metro_fare = transit_fares.get("metro", "$2.00")
            bus_fare = transit_fares.get("bus", "$1.50")
            transit_minutes = max(10, int(drive_minutes * 1.4))

            if "metro" in want:
                routes.append({
                    "type": "metro",
                    "provider": f"{city} Metro",
                    "duration_minutes": transit_minutes,
                    "cost_estimate": metro_fare,
                    "description": f"Take the metro. Estimated {transit_minutes} min including transfers.",
                    "booking_link": None,
                })

            if "bus" in want:
                routes.append({
                    "type": "bus",
                    "provider": f"{city} Bus",
                    "duration_minutes": int(transit_minutes * 1.2),
                    "cost_estimate": bus_fare,
                    "description": f"Take a local bus. Estimated {int(transit_minutes * 1.2)} min.",
                    "booking_link": None,
                })

        if "taxi" in want or "rideshare" in want:
            fare = ride_rates["base"] + dist_km * ride_rates["per_km"]
            fare_low = round(fare * 0.85, 1)
            fare_high = round(fare * 1.25, 1)

            if "rideshare" in want:
                routes.append({
                    "type": "rideshare",
                    "provider": "Uber / local rideshare",
                    "duration_minutes": drive_minutes,
                    "cost_estimate": f"${fare_low}–${fare_high}",
                    "description": f"Rideshare app. {drive_minutes} min, estimated ${fare_low}–${fare_high} USD.",
                    "booking_link": "https://m.uber.com/",
                })

            if "taxi" in want:
                taxi_fare_low = round(fare_low * 1.1, 1)
                taxi_fare_high = round(fare_high * 1.3, 1)
                routes.append({
                    "type": "taxi",
                    "provider": "Local taxi",
                    "duration_minutes": drive_minutes,
                    "cost_estimate": f"${taxi_fare_low}–${taxi_fare_high}",
                    "description": f"Street taxi or pre-booked cab. {drive_minutes} min.",
                    "booking_link": None,
                })

        return {"routes": routes, "origin": origin, "destination": destination}

    except Exception as e:
        return {"error": str(e), "routes": []}
