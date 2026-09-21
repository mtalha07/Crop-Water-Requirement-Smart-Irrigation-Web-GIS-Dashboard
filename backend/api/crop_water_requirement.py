"""Illustrative crop model using a live forecast and an explicit rainfall assumption."""
import math
from backend.api.open_meteo_api import fetch_soil_and_weather_data

CROP_COEFFICIENTS = {
    "wheat": {"initial": 0.3, "mid": 1.15, "late": 0.25},
    "rice": {"initial": 1.05, "mid": 1.2, "late": 0.75},
    "corn": {"initial": 0.4, "mid": 1.2, "late": 0.5},
    "maize": {"initial": 0.4, "mid": 1.1, "late": 0.5},
    "potato": {"initial": 0.5, "mid": 1.1, "late": 0.8},
    "tomato": {"initial": 0.6, "mid": 1.15, "late": 0.7},
    "cotton": {"initial": 0.5, "mid": 1.2, "late": 0.65},
    "sugarcane": {"initial": 0.8, "mid": 1.3, "late": 0.9},
    "banana": {"initial": 0.7, "mid": 1.25, "late": 0.85},
    "apple": {"initial": 0.65, "mid": 1.15, "late": 0.6},
}


def calculate_crop_water_requirement(crop_type, lat, lon, stage, rainfall_effectiveness=80.0):
    if not math.isfinite(rainfall_effectiveness) or not 0 <= rainfall_effectiveness <= 100:
        raise ValueError("Rainfall effectiveness must be between 0 and 100 percent.")
    data = fetch_soil_and_weather_data(lat, lon)
    return calculate_from_weather(crop_type, stage, data, rainfall_effectiveness, lat, lon)


def calculate_from_weather(crop_type, stage, data, rainfall_effectiveness, lat, lon):
    """Shared point and polygon formula; callers validate user inputs."""
    coefficient = CROP_COEFFICIENTS[crop_type][stage]
    crop_et = data["evapotranspiration"] * coefficient
    effective_rainfall = data["rainfall"] * rainfall_effectiveness / 100.0
    required = max(0.0, crop_et - effective_rainfall)
    return {
        "required_water": round(required, 2),
        "required_water_unrounded": required,
        "unit": "mm/day",
        "crop_coefficient": coefficient,
        "reference_et": data["evapotranspiration"],
        "effective_rainfall": round(effective_rainfall, 3),
        "rainfall": data["rainfall"],
        "rainfall_effectiveness": rainfall_effectiveness,
        "forecast_date": data["forecast_date"],
        "timezone": data["timezone"],
        "fetched_at": data["fetched_at"],
        "latitude": lat,
        "longitude": lon,
        "weather_live": data["weather_live"],
        "source": data["source"],
        "demo": True,  # Crop coefficients and rainfall model still need local validation.
    }
