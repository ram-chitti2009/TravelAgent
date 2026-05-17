import json
from .flights import search_flights, FLIGHT_SCHEMA
from .hotels import search_hotels, HOTEL_SCHEMA
from .restaurants import search_restaurants, RESTAURANT_SCHEMA
from .weather import get_weather, WEATHER_SCHEMA
from .maps import get_distance, MAPS_SCHEMA
from .transport import get_local_transport, TRANSPORT_SCHEMA
from .intercity import search_intercity_travel, INTERCITY_SCHEMA
from .attractions import search_attractions, ATTRACTIONS_SCHEMA

ALL_TOOLS = [
    FLIGHT_SCHEMA,
    HOTEL_SCHEMA,
    RESTAURANT_SCHEMA,
    WEATHER_SCHEMA,
    MAPS_SCHEMA,
    TRANSPORT_SCHEMA,
    INTERCITY_SCHEMA,
    ATTRACTIONS_SCHEMA,
]

TOOL_REGISTRY = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "search_restaurants": search_restaurants,
    "get_weather": get_weather,
    "get_distance": get_distance,
    "get_local_transport": get_local_transport,
    "search_intercity_travel": search_intercity_travel,
    "search_attractions": search_attractions,
}


def execute_tool(tool_name: str, arguments: dict | str) -> dict:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            arguments = {}

    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(**arguments)
    except Exception as e:
        return {"error": str(e)}
