"""Check raw serpapi response structure for restaurants and attractions."""
import json
from dotenv import load_dotenv
load_dotenv()
import serpapi

# Check restaurants raw
r = serpapi.search({
    "engine": "google_maps",
    "q": "Japanese restaurants near Shinjuku Tokyo",
    "type": "search",
    "hl": "en",
    "api_key": __import__("os").getenv("SERPAPI_API_KEY"),
})
results = r.get("local_results", [])
if results:
    print("RESTAURANT KEYS:", list(results[0].keys()))
    print(json.dumps(results[0], indent=2)[:1000])
