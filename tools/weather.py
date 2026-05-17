import os
import requests
from datetime import datetime


WEATHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "Get weather forecast for a travel destination and generate packing "
            "recommendations based on expected conditions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Paris' or 'Tokyo'",
                },
                "travel_date": {
                    "type": "string",
                    "description": "Start date of travel in YYYY-MM-DD format to get relevant forecast window",
                },
                "country_code": {
                    "type": "string",
                    "description": "ISO 3166 2-letter country code to disambiguate city names, e.g. 'FR' for France",
                },
            },
            "required": ["city"],
        },
    },
}


def _packing_tips(forecast: list) -> list:
    tips = set()
    for day in forecast:
        temp_high = day.get("temp_high_c", 20)
        condition = day.get("condition", "").lower()
        humidity = day.get("humidity_pct", 50)
        wind = day.get("wind_speed_kmh", 0)

        if "rain" in condition or "drizzle" in condition or "shower" in condition:
            tips.add("Umbrella or compact rain jacket")
        if temp_high < 5:
            tips.add("Heavy winter coat, gloves, and scarf")
        elif temp_high < 15:
            tips.add("Warm jacket and layers")
        elif temp_high < 22:
            tips.add("Light jacket for cooler evenings")
        else:
            tips.add("Lightweight, breathable clothing")
        if temp_high > 25:
            tips.add("Sunscreen (SPF 30+) and a hat")
        if humidity > 80:
            tips.add("Breathable, moisture-wicking fabrics")
        if wind > 40:
            tips.add("Windproof outer layer")
        if "snow" in condition:
            tips.add("Waterproof boots and warm socks")

    return list(tips)


def get_weather(
    city: str,
    travel_date: str = None,
    country_code: str = None,
) -> dict:
    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        q = f"{city},{country_code}" if country_code else city

        url = "https://api.openweathermap.org/data/2.5/forecast"
        resp = requests.get(url, params={"q": q, "appid": api_key, "units": "metric", "cnt": 40}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Group 3-hour blocks by date, keep midday reading
        by_date: dict = {}
        for entry in data.get("list", []):
            date_str = entry["dt_txt"].split(" ")[0]
            hour = int(entry["dt_txt"].split(" ")[1].split(":")[0])
            if date_str not in by_date or abs(hour - 12) < abs(
                int(by_date[date_str]["dt_txt"].split(" ")[1].split(":")[0]) - 12
            ):
                by_date[date_str] = entry

        forecast = []
        for date_str, entry in sorted(by_date.items()):
            main = entry["main"]
            weather = entry["weather"][0]
            wind_ms = entry.get("wind", {}).get("speed", 0)
            temp_c_high = main["temp_max"]
            temp_c_low = main["temp_min"]

            forecast.append({
                "date": date_str,
                "condition": weather["main"],
                "description": weather["description"],
                "temp_high_c": round(temp_c_high, 1),
                "temp_low_c": round(temp_c_low, 1),
                "temp_high_f": round(temp_c_high * 9 / 5 + 32, 1),
                "temp_low_f": round(temp_c_low * 9 / 5 + 32, 1),
                "humidity_pct": main["humidity"],
                "wind_speed_kmh": round(wind_ms * 3.6, 1),
                "icon_url": f"https://openweathermap.org/img/wn/{weather['icon']}@2x.png",
            })

        city_info = data.get("city", {})

        # If travel date is more than 5 days out, live forecast is irrelevant —
        # return seasonal averages for the actual travel month instead
        if travel_date:
            try:
                travel_dt = datetime.strptime(travel_date, "%Y-%m-%d")
                days_out = (travel_dt - datetime.now()).days
                if days_out > 5:
                    return _seasonal_fallback(
                        city_info.get("name", city),
                        city_info.get("country", country_code or ""),
                        travel_date,
                        reason="future",
                    )
            except ValueError:
                pass

        return {
            "city": city_info.get("name", city),
            "country": city_info.get("country", ""),
            "forecast": forecast[:5],
            "packing_tips": _packing_tips(forecast[:5]),
        }

    except Exception as e:
        return _seasonal_fallback(city, country_code, travel_date, str(e))


# Monthly seasonal averages for common destinations (temp in °C)
_SEASONAL = {
    "tokyo": {6: (22,17), 7: (29,24), 8: (31,25), 12: (12,5), 1: (9,2)},
    "paris": {6: (22,14), 7: (25,16), 8: (25,16), 12: (8,3), 1: (6,2)},
    "new york": {6: (26,18), 7: (29,22), 8: (28,21), 12: (7,1), 1: (3,-2)},
    "london": {6: (20,13), 7: (23,15), 8: (22,15), 12: (8,4), 1: (7,3)},
    "dubai": {6: (38,29), 7: (41,31), 8: (41,31), 12: (24,16), 1: (22,14)},
    "sydney": {6: (16,10), 7: (16,9), 12: (25,18), 1: (26,19)},
    "bangkok": {6: (33,27), 7: (32,26), 12: (30,21), 1: (30,20)},
}

_JULY_PACKING = [
    "Lightweight, breathable clothing",
    "Sunscreen (SPF 30+) and a hat",
    "Compact umbrella (summer showers)",
    "Comfortable walking shoes",
]


def _seasonal_fallback(city: str, country_code: str, travel_date: str, err: str = "", reason: str = "error") -> dict:
    from datetime import datetime as dt
    month = 7  # default July
    if travel_date:
        try:
            month = dt.strptime(travel_date, "%Y-%m-%d").month
        except ValueError:
            pass

    city_key = city.lower()
    avgs = _SEASONAL.get(city_key, {}).get(month)
    if not avgs:
        # Generic tropical/temperate estimate
        avgs = (26, 18)

    high_c, low_c = avgs
    from datetime import date, timedelta, datetime as dt2
    travel_dt = None
    if travel_date:
        try:
            travel_dt = dt2.strptime(travel_date, "%Y-%m-%d")
        except ValueError:
            pass

    base = date.today()
    forecast = []
    for i in range(5):
        d = base + timedelta(days=i)
        forecast.append({
            "date": d.isoformat(),
            "condition": "Partly Cloudy",
            "description": "seasonal average",
            "temp_high_c": high_c,
            "temp_low_c": low_c,
            "temp_high_f": round(high_c * 9 / 5 + 32, 1),
            "temp_low_f": round(low_c * 9 / 5 + 32, 1),
            "humidity_pct": 70,
            "wind_speed_kmh": 15,
            "icon_url": "",
        })

    return {
        "city": city,
        "country": country_code or "",
        "forecast": forecast,
        "packing_tips": _JULY_PACKING,
        "note": (
            f"Showing seasonal averages for {city} in {travel_dt.strftime('%B') if travel_dt else 'your travel month'}"
            f" — live forecasts are only available within 5 days of departure."
            if reason == "future"
            else f"Live forecast unavailable. Showing seasonal averages for {city}."
        ),
    }
