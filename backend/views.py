import math
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from backend.models import Pole
from backend.api.open_meteo_api import WeatherDataError
from backend.api.polygon_water import calculate_polygon_water
from backend.api.crop_water_requirement import (
    CROP_COEFFICIENTS, calculate_crop_water_requirement,
)


@require_GET
def dashboard(request):
    return render(request, "index.html", {"crops": list(CROP_COEFFICIENTS)})


@require_POST
def calculate_water(request):
    crop = request.POST.get("crop", "").strip().lower()
    stage = request.POST.get("stage", "").strip().lower()
    if crop not in CROP_COEFFICIENTS:
        return JsonResponse({"error": "Select a supported crop."}, status=400)
    if stage not in CROP_COEFFICIENTS[crop]:
        return JsonResponse({"error": "Select a supported growth stage."}, status=400)
    mode = request.POST.get("mode", "point")
    if mode not in ("point", "polygon"):
        return JsonResponse({"error": "Select point or polygon mode."}, status=400)
    try:
        effectiveness = float(request.POST.get("rainfall_effectiveness", "80"))
        if not math.isfinite(effectiveness) or not 0 <= effectiveness <= 100:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Rainfall effectiveness must be between 0 and 100 percent."}, status=400)
    try:
        if mode == "polygon":
            raw_geometry = request.POST.get("polygon", "")
            if len(raw_geometry) > 50000:
                raise ValueError("The field boundary is too complex. Use at most 500 corners.")
            try:
                geometry = json.loads(raw_geometry)
            except (ValueError, RecursionError):
                raise ValueError("Draw a valid field polygon before calculating.")
            result = calculate_polygon_water(crop, stage, geometry, effectiveness)
        else:
            try:
                lat = float(request.POST.get("lat", ""))
                lon = float(request.POST.get("lon", ""))
            except (ValueError, TypeError):
                raise ValueError("Enter a valid latitude and longitude.")
            if not (math.isfinite(lat) and math.isfinite(lon)
                    and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Coordinates are outside the valid range.")
            result = calculate_crop_water_requirement(crop, lat, lon, stage, effectiveness)
            result["mode"] = "point"
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except WeatherDataError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    return JsonResponse(result)


@require_GET
def fetch_spatial_data(request):
    poles = [{
        "PoleID": pole.pole_id,
        "PoleSurveyNumber": pole.pole_survey_number,
        "latitude": pole.latitude,
        "longitude": pole.longitude,
        "description": pole.description,
    } for pole in Pole.objects.all()[:100]]
    return JsonResponse({"poles": poles, "source": "Local SQLite demo data"})
