from __future__ import annotations

from typing import Any

import httpx

_OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
_OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"


def _geocode_city(city: str) -> dict[str, float] | None:
    try:
        resp = httpx.get(
            _OPEN_METEO_GEOCODING,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    results = data.get("results")
    if not results:
        return None

    r = results[0]
    return {
        "lat": r["latitude"],
        "lon": r["longitude"],
        "name": r.get("name", city),
        "country": r.get("country", ""),
    }


def _fahrenheit_to_celsius(f: float) -> float:
    return round((f - 32) * 5 / 9, 1)


def scrape_weather(city: str) -> dict[str, Any]:
    geo = _geocode_city(city)
    if geo is None:
        return {"error": f"Could not geocode city: {city}"}

    params = {
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
            "pressure_msl",
        ],
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "wind_speed_10m_max",
        ],
        "timezone": "auto",
        "forecast_days": 3,
    }

    try:
        resp = httpx.get(_OPEN_METEO_FORECAST, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"error": f"Weather API request failed: {e}"}

    current = data.get("current", {})
    daily = data.get("daily", {})

    weather_code_map = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Depositing rime fog", 51: "Light drizzle",
        53: "Moderate drizzle", 55: "Dense drizzle", 56: "Light freezing drizzle",
        57: "Dense freezing drizzle", 61: "Slight rain", 63: "Moderate rain",
        65: "Heavy rain", 66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
        77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    result: dict[str, Any] = {
        "location": geo["name"],
        "country": geo["country"],
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "pressure_hpa": current.get("pressure_msl"),
            "condition": weather_code_map.get(current.get("weather_code"), "Unknown"),
        },
        "forecast": [],
    }

    if daily:
        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        precip = daily.get("precipitation_sum", [])
        winds = daily.get("wind_speed_10m_max", [])

        for i in range(len(dates) if dates else 0):
            result["forecast"].append({
                "date": dates[i] if i < len(dates) else "",
                "high_c": max_temps[i] if i < len(max_temps) else None,
                "low_c": min_temps[i] if i < len(min_temps) else None,
                "condition": weather_code_map.get(codes[i] if i < len(codes) else 0, "Unknown"),
                "precipitation_mm": precip[i] if i < len(precip) else None,
                "wind_max_kmh": winds[i] if i < len(winds) else None,
            })

    current_temp = result["current"]["temperature_c"]
    if current_temp is not None:
        result["current"]["temperature_f"] = round(current_temp * 9 / 5 + 32, 1)

    return result


def register_search_tools(registry: Any) -> None:
    registry.register(
        name="scrape_weather",
        description="Get current weather and 3-day forecast for any city using Open-Meteo (free, no API key).",
        params_schema={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g. Istanbul, London, New York)",
                },
            },
            "required": ["city"],
        },
        handler=scrape_weather,
    )
