"""Fetch today's location-specific forecast from Open-Meteo (not OpenWeather)."""
import json
import math
import ssl
import truststore
from datetime import date, datetime, timezone
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherDataError(Exception):
    """The weather provider is unavailable or returned unusable data."""


def fetch_soil_and_weather_data(lat, lon):
    """Legacy name; fetch weather only, with no soil measurements.

    Daily totals cover today's entire day in the location's timezone, including
    forecast hours. Rain excludes snow. The caller estimates effective rainfall.
    """
    return fetch_weather_for_locations([(lat, lon)])[0]


def fetch_weather_for_locations(locations):
    """Fetch up to nine (latitude, longitude) samples in one API request."""
    if not 1 <= len(locations) <= 9:
        raise ValueError("Provide between one and nine weather locations.")
    params = urlencode({
        "latitude": ",".join(str(lat) for lat, lon in locations),
        "longitude": ",".join(str(lon) for lat, lon in locations),
        "daily": "et0_fao_evapotranspiration,rain_sum,showers_sum",
        "timezone": "auto",
        "forecast_days": 1,
        "precipitation_unit": "mm",
    })
    request = Request(
        OPEN_METEO_URL + "?" + params,
        headers={"User-Agent": "SmartIrrigationDemo/1.0", "Accept": "application/json"},
    )
    try:
        # The external weather API call happens here, once per calculation.
        # Validate against the operating system's trusted certificate store.
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with urlopen(request, timeout=10, context=context) as response:
            payload = json.load(response)
    except (URLError, OSError, HTTPException, ValueError) as exc:
        raise WeatherDataError(
            "Unable to fetch Open-Meteo weather. Check your internet connection "
            "and try again shortly. No simulated weather was substituted."
        ) from exc

    payloads = payload if isinstance(payload, list) else [payload]
    if len(payloads) != len(locations):
        raise WeatherDataError("Open-Meteo did not return weather for every field sample. Try again later.")
    return [_parse_daily_weather(item) for item in payloads]


def _parse_daily_weather(payload):
    try:
        daily = payload["daily"]
        units = payload["daily_units"]

        def daily_number(name):
            value = daily[name][0]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0 or units[name] != "mm"):
                raise ValueError("Invalid daily weather value or unit")
            return float(value)

        et0 = daily_number("et0_fao_evapotranspiration")
        rainfall = daily_number("rain_sum") + daily_number("showers_sum")
        forecast_date = date.fromisoformat(daily["time"][0]).isoformat()
        location_timezone = payload["timezone"]
        if not isinstance(location_timezone, str) or not location_timezone:
            raise ValueError("Missing timezone")
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise WeatherDataError(
            "Open-Meteo returned incomplete or invalid daily weather. "
            "Please try again later. No result was calculated."
        ) from exc

    return {
        "evapotranspiration": et0,
        "rainfall": rainfall,
        "forecast_date": forecast_date,
        "timezone": location_timezone,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Open-Meteo daily forecast; weather-model estimates, not field sensors.",
        "weather_live": True,
    }
