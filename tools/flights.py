import os
import serpapi


FLIGHT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": (
            "Search for available flights between two airports or cities on a given date. "
            "Returns best and alternate flight options with prices, durations, and airline info."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Departure airport IATA code or city name, e.g. 'JFK' or 'New York'",
                },
                "destination": {
                    "type": "string",
                    "description": "Arrival airport IATA code or city name, e.g. 'CDG' or 'Paris'",
                },
                "departure_date": {
                    "type": "string",
                    "description": "Departure date in YYYY-MM-DD format",
                },
                "return_date": {
                    "type": "string",
                    "description": "Return date in YYYY-MM-DD format for round trips. Omit for one-way.",
                },
                "adults": {
                    "type": "integer",
                    "description": "Number of adult passengers",
                    "default": 1,
                },
                "currency": {
                    "type": "string",
                    "description": "Currency code for prices, e.g. 'USD', 'EUR'",
                    "default": "USD",
                },
            },
            "required": ["origin", "destination", "departure_date"],
        },
    },
}


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    adults: int = 1,
    currency: str = "USD",
) -> dict:
    try:
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "adults": adults,
            "currency": currency,
            "hl": "en",
            "type": "1" if return_date else "2",
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }
        if return_date:
            params["return_date"] = return_date

        results = serpapi.search(params)

        flights = []
        for group in [results.get("best_flights", []), results.get("other_flights", [])]:
            for item in group:
                if not item.get("flights"):
                    continue
                first_leg = item["flights"][0]
                last_leg = item["flights"][-1]
                flights.append({
                    "airline": first_leg.get("airline", "Unknown"),
                    "price": item.get("price", 0),
                    "currency": currency,
                    "duration_minutes": item.get("total_duration", 0),
                    "stops": len(item.get("layovers", [])),
                    "departure_time": first_leg.get("departure_airport", {}).get("time", ""),
                    "arrival_time": last_leg.get("arrival_airport", {}).get("time", ""),
                    "airline_logo": first_leg.get("airline_logo", ""),
                    "booking_token": results.get("search_metadata", {}).get("google_flights_url", ""),
                })
            if len(flights) >= 5:
                break

        return {
            "best_flights": flights[:5],
            "search_metadata": {
                "origin": origin,
                "destination": destination,
                "date": departure_date,
            },
        }

    except Exception as e:
        return {"error": str(e), "best_flights": []}
