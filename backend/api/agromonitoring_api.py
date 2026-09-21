"""Compatibility import for the former weather module; no AgroMonitoring calls."""
from .open_meteo_api import WeatherDataError, fetch_soil_and_weather_data

__all__ = ["WeatherDataError", "fetch_soil_and_weather_data"]
