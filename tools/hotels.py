import os
import serpapi


HOTEL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_hotels",
        "description": (
            "Search for hotels or accommodations at a destination for given check-in and check-out dates. "
            "Returns options with prices, ratings, amenities, and booking links."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "City or area to search hotels in, e.g. 'Paris, France'",
                },
                "check_in": {
                    "type": "string",
                    "description": "Check-in date in YYYY-MM-DD format",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out date in YYYY-MM-DD format",
                },
                "adults": {
                    "type": "integer",
                    "description": "Number of adult guests",
                    "default": 2,
                },
                "min_rating": {
                    "type": "number",
                    "description": "Minimum hotel rating out of 10. Only pass this if the user explicitly requests luxury or highly rated hotels. Default: omit this to show all price ranges.",
                },
                "currency": {
                    "type": "string",
                    "default": "USD",
                },
            },
            "required": ["destination", "check_in", "check_out"],
        },
    },
}


def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    min_rating: float = None,
    currency: str = "USD",
) -> dict:
    try:
        params = {
            "engine": "google_hotels",
            "q": f"hotels in {destination}",
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adults,
            "currency": currency,
            "hl": "en",
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }

        results = serpapi.search(params)

        hotels = []
        for h in results.get("properties", []):
            rating = h.get("overall_rating", 0)
            # ratings from SerpAPI are on a 5-star scale; only filter if explicitly set
            if min_rating and rating < (min_rating / 2):
                continue

            rate = h.get("rate_per_night", {})
            total = h.get("total_rate", {})

            price_per_night = rate.get("extracted_lowest", 0)
            total_price = total.get("extracted_lowest", 0)

            images = h.get("images", [])
            image_url = ""
            if images:
                first = images[0]
                image_url = first.get("thumbnail", "") if isinstance(first, dict) else str(first)

            hotels.append({
                "name": h.get("name", ""),
                "rating": rating,
                "reviews": h.get("reviews", 0),
                "price_per_night": price_per_night,
                "total_price": total_price,
                "currency": currency,
                "description": h.get("description", ""),
                "amenities": h.get("amenities", [])[:6],
                "image_url": image_url,
                "booking_link": h.get("link", ""),
                "latitude": h.get("gps_coordinates", {}).get("latitude"),
                "longitude": h.get("gps_coordinates", {}).get("longitude"),
            })

            if len(hotels) >= 5:
                break

        return {"hotels": hotels}

    except Exception as e:
        return {"error": str(e), "hotels": []}
