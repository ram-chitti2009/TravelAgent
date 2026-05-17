import os
import serpapi


RESTAURANT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_restaurants",
        "description": (
            "Find restaurants and food options at a location. "
            "Can filter by cuisine type, meal time, and budget level."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City, neighborhood, or address to search near, e.g. 'Eiffel Tower, Paris'",
                },
                "cuisine": {
                    "type": "string",
                    "description": "Cuisine type filter, e.g. 'French', 'Italian', 'sushi'",
                },
                "meal_type": {
                    "type": "string",
                    "enum": ["breakfast", "brunch", "lunch", "dinner", "cafe", "bar"],
                    "description": "Type of meal or dining experience",
                },
                "budget": {
                    "type": "string",
                    "enum": ["$", "$$", "$$$", "$$$$"],
                    "description": "Price level from cheapest ($) to most expensive ($$$$)",
                },
            },
            "required": ["location"],
        },
    },
}


def search_restaurants(
    location: str,
    cuisine: str = None,
    meal_type: str = None,
    budget: str = None,
) -> dict:
    try:
        query_parts = ["restaurants"]
        if cuisine:
            query_parts.insert(0, cuisine)
        if meal_type:
            query_parts.append(meal_type)
        query_parts.append(f"near {location}")
        query = " ".join(query_parts)

        params = {
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "hl": "en",
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }

        results = serpapi.search(params)

        restaurants = []
        for r in results.get("local_results", []):
            price = r.get("price", "")
            if budget and price and price != budget:
                continue

            coords = r.get("gps_coordinates", {})
            maps_link = (
                f"https://www.google.com/maps?q={coords['latitude']},{coords['longitude']}"
                if coords.get("latitude") else ""
            )

            restaurants.append({
                "name": r.get("title", ""),
                "cuisine": r.get("type", ""),
                "rating": r.get("rating", 0),
                "reviews": r.get("reviews", 0),
                "price_level": price,
                "address": r.get("address", ""),
                "hours": r.get("hours", ""),
                "phone": r.get("phone", ""),
                "website": r.get("website", ""),
                "image_url": r.get("thumbnail", ""),
                "maps_link": maps_link,
            })

            if len(restaurants) >= 6:
                break

        return {"restaurants": restaurants}

    except Exception as e:
        return {"error": str(e), "restaurants": []}
