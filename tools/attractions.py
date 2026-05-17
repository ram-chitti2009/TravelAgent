import os
import serpapi


ATTRACTIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_attractions",
        "description": (
            "Find top tourist attractions, things to do, and places to visit at a destination. "
            "Can filter by category such as museums, outdoor, nightlife, shopping, or family-friendly. "
            "Use this whenever a user asks what to do, where to go, or what to see at a destination."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "City or area to find attractions in, e.g. 'Paris' or 'Kyoto, Japan'",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "museums",
                        "outdoor",
                        "nightlife",
                        "shopping",
                        "family",
                        "historical",
                        "art",
                        "food tours",
                        "adventure",
                        "beaches",
                    ],
                    "description": "Category filter for attraction type",
                },
                "budget": {
                    "type": "string",
                    "enum": ["free", "budget", "moderate", "expensive"],
                    "description": "Budget level — 'free' for no-cost attractions, 'budget' for under $20, etc.",
                },
            },
            "required": ["destination"],
        },
    },
}


def search_attractions(
    destination: str,
    category: str = None,
    budget: str = None,
) -> dict:
    try:
        # Build query
        query_parts = ["top things to do in", destination]
        if category:
            query_parts = [category, "attractions in", destination]
        if budget == "free":
            query_parts.append("free")
        query = " ".join(query_parts)

        params = {
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "hl": "en",
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }

        results = serpapi.search(params)

        attractions = []
        for place in results.get("local_results", []):
            # Filter out restaurants/hotels from attraction results
            place_type = place.get("type", "").lower()
            if any(word in place_type for word in ["restaurant", "hotel", "motel", "food"]):
                continue

            price_text = place.get("price", "")
            if budget == "free" and price_text and price_text not in ["Free", "$0", ""]:
                continue

            coords = place.get("gps_coordinates", {})
            maps_link = (
                f"https://www.google.com/maps?q={coords['latitude']},{coords['longitude']}"
                if coords.get("latitude") else ""
            )

            # description from extensions if available
            extensions = place.get("extensions", [])
            description = extensions[0] if extensions and isinstance(extensions[0], str) else ""

            attractions.append({
                "name": place.get("title", ""),
                "type": place.get("type", "Attraction"),
                "rating": place.get("rating", 0),
                "reviews": place.get("reviews", 0),
                "address": place.get("address", ""),
                "hours": place.get("hours", ""),
                "price": price_text or ("Free" if budget == "free" else "See website"),
                "description": description,
                "image_url": place.get("thumbnail", ""),
                "maps_link": maps_link,
                "website": place.get("website", ""),
                "latitude": coords.get("latitude"),
                "longitude": coords.get("longitude"),
            })

            if len(attractions) >= 8:
                break

        # Fallback: use Google organic search if Maps returns nothing
        if not attractions:
            params2 = {
                "engine": "google",
                "q": query,
                "api_key": os.getenv("SERPAPI_API_KEY"),
            }
            results2 = serpapi.search(params2)

            for r in results2.get("organic_results", [])[:6]:
                attractions.append({
                    "name": r.get("title", ""),
                    "type": "Attraction",
                    "rating": None,
                    "reviews": None,
                    "address": destination,
                    "hours": "",
                    "price": "",
                    "description": r.get("snippet", "")[:250],
                    "image_url": "",
                    "maps_link": "",
                    "website": r.get("link", ""),
                    "latitude": None,
                    "longitude": None,
                })

        return {"attractions": attractions, "destination": destination}

    except Exception as e:
        return {"error": str(e), "attractions": []}
