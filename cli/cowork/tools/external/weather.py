"""
🌤️ Weather Tools
Implementations for OpenWeatherMap.
"""

import urllib.parse
from .utils import _env, _missing_key, _http_get, _TTL_WEATHER, json_to_markdown

def openweather_current(location: str, units: str = "metric") -> str:
    """Get current weather conditions using OpenWeatherMap API."""
    api_key = _env("OPENWEATHER_API_KEY")
    if not api_key: return _missing_key("openweather_current", "OPENWEATHER_API_KEY")

    params = urllib.parse.urlencode({"q": location, "appid": api_key, "units": units})
    url = f"https://api.openweathermap.org/data/2.5/weather?{params}"

    try:
        data = _http_get(url, ttl=_TTL_WEATHER)
        if data.get("cod") not in (200, "200"): return f"Error: {data.get('message')}"
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        return f"🌤️ **Weather** for {data.get('name')}: {weather.get('description')}, {main.get('temp')}°C"
    except Exception as e:
        return f"Weather failed: {e}"

def openweather_forecast(location: str, days: int = 5) -> str:
    """Get weather forecast using OpenWeatherMap API."""
    api_key = _env("OPENWEATHER_API_KEY")
    if not api_key: return _missing_key("openweather_forecast", "OPENWEATHER_API_KEY")

    params = urllib.parse.urlencode({"q": location, "appid": api_key, "units": "metric", "cnt": days * 8})
    url = f"https://api.openweathermap.org/data/2.5/forecast?{params}"

    try:
        data = _http_get(url, ttl=_TTL_WEATHER)
        if data.get("cod") not in (200, "200"): return f"Error: {data.get('message')}"
        
        # We can directly transform the response into markdown
        # To make it concise, let's extract only the list of forecasts and city details
        simplified_data = {
            "City": data.get("city", {}).get("name"),
            "Forecasts": [
                {
                    "Time": item.get("dt_txt"),
                    "Temp": f"{item.get('main', {}).get('temp')}°C",
                    "Weather": item.get("weather", [{}])[0].get("description"),
                    "Humidity": f"{item.get('main', {}).get('humidity')}%"
                }
                for item in data.get("list", [])
            ]
        }
        
        md_output = f"📅 **Weather Forecast for {location} (Next {days} days):**\n\n"
        md_output += json_to_markdown(simplified_data)
        return md_output
    except Exception as e:
        return f"Forecast failed: {e}"

TOOLS = [
    {
        "category": "WEATHER_TOOLS",
        "type": "function",
        "function": {
            "name": "openweather_current",
            "description": "Get current weather using OpenWeatherMap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "category": "WEATHER_TOOLS",
        "type": "function",
        "function": {
            "name": "openweather_forecast",
            "description": "Get 5-day weather forecast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        },
    },
]
