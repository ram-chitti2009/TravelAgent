"""Quick CLI test for all tools. Run: python test_tools.py"""
import json
from dotenv import load_dotenv
load_dotenv()

from tools.flights import search_flights
from tools.hotels import search_hotels
from tools.weather import get_weather
from tools.restaurants import search_restaurants
from tools.attractions import search_attractions

def section(name):
    print(f"\n{'='*50}\n{name}\n{'='*50}")

section("FLIGHTS")
f = search_flights("JFK", "NRT", "2026-07-01", return_date="2026-07-06")
print(json.dumps(f, indent=2)[:800])

section("HOTELS")
h = search_hotels("Tokyo, Japan", "2026-07-01", "2026-07-06", adults=2)
print(json.dumps(h, indent=2)[:800])

section("WEATHER")
w = get_weather("Tokyo", country_code="JP")
print(json.dumps(w, indent=2)[:800])

section("RESTAURANTS")
r = search_restaurants("Shinjuku, Tokyo", cuisine="Japanese", meal_type="dinner")
print(json.dumps(r, indent=2)[:800])

section("ATTRACTIONS")
a = search_attractions("Tokyo")
print(json.dumps(a, indent=2)[:800])
