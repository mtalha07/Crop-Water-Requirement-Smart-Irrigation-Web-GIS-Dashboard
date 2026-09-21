"""Estimate whole-field water volume from area-weighted weather samples."""
import math
from pyproj import CRS, Geod, Transformer
from shapely.geometry import Polygon, box
from shapely.ops import transform

from .crop_water_requirement import calculate_from_weather
from .open_meteo_api import WeatherDataError, fetch_weather_for_locations


def prepare_polygon_samples(geometry):
    """Validate a simple WGS84 GeoJSON Polygon, then clip a 3 by 3 grid to it."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("Draw a polygon before calculating the field.")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise ValueError("Draw one continuous field boundary without holes.")
    ring = rings[0]
    if not 4 <= len(ring) <= 501:
        raise ValueError("Draw a closed field with 3 to 500 corners.")
    for point in ring:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) for v in point)
                or not -180 <= point[0] <= 180 or not -85 <= point[1] <= 85):
            raise ValueError("The field contains invalid longitude/latitude coordinates.")
    if ring[0] != ring[-1]:
        raise ValueError("The field boundary must be closed.")
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.is_empty or polygon.area == 0:
        raise ValueError("Draw a valid field boundary; edges must not cross or overlap.")
    west, south, east, north = polygon.bounds
    if east - west > 2 or north - south > 2:
        raise ValueError("Draw a local field spanning less than 2 degrees of latitude/longitude. Date-line crossings are not supported.")
    area_m2 = abs(Geod(ellps="WGS84").geometry_area_perimeter(polygon)[0])
    if not math.isfinite(area_m2) or area_m2 < 1:
        raise ValueError("The field must cover at least 1 square metre.")

    centre = polygon.centroid
    local_crs = CRS.from_proj4(
        f"+proj=laea +lat_0={centre.y} +lon_0={centre.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    backward = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True)
    field = transform(forward.transform, polygon)
    xmin, ymin, xmax, ymax = field.bounds
    samples = []
    for row in range(3):
        for col in range(3):
            cell = box(xmin + (xmax - xmin) * col / 3,
                       ymin + (ymax - ymin) * row / 3,
                       xmin + (xmax - xmin) * (col + 1) / 3,
                       ymin + (ymax - ymin) * (row + 1) / 3)
            part = field.intersection(cell)
            if part.is_empty or part.area <= 0:
                continue
            # representative_point stays inside a concave or disconnected clipped cell.
            point = part.representative_point()
            lon, lat = backward.transform(point.x, point.y)
            samples.append({"latitude": lat, "longitude": lon, "weight": part.area})
    total_weight = sum(sample["weight"] for sample in samples)
    for sample in samples:
        # Preserve the geodesic total; use local equal-area cell fractions as weights.
        sample["area_m2"] = area_m2 * sample.pop("weight") / total_weight
    return area_m2, samples


def calculate_polygon_water(crop, stage, geometry, rainfall_effectiveness):
    area_m2, samples = prepare_polygon_samples(geometry)
    forecasts = fetch_weather_for_locations([
        (sample["latitude"], sample["longitude"]) for sample in samples
    ])
    if len(forecasts) != len(samples) or len({f["forecast_date"] for f in forecasts}) != 1:
        raise WeatherDataError("Weather samples must cover the same day and every part of the field. Please try again later.")
    total_litres = 0.0
    for index, (sample, forecast) in enumerate(zip(samples, forecasts), start=1):
        result = calculate_from_weather(crop, stage, forecast, rainfall_effectiveness,
                                        sample["latitude"], sample["longitude"])
        # 1 mm over 1 square metre equals 1 litre. Clamp each cell before summing.
        litres = result["required_water_unrounded"] * sample["area_m2"]
        total_litres += litres
        sample.update({
            "id": index,
            "required_water": result["required_water"],
            "reference_et": result["reference_et"],
            "effective_rainfall": result["effective_rainfall"],
            "rainfall": result["rainfall"],
            "volume_m3": litres / 1000,
        })
    return {
        "mode": "polygon", "area_m2": area_m2, "area_hectares": area_m2 / 10000,
        "required_water": round(total_litres / area_m2, 2), "unit": "mm/day",
        "total_water_litres": round(total_litres, 2),
        "total_water_m3": round(total_litres / 1000, 3),
        "sample_count": len(samples), "samples": samples,
        "forecast_date": forecasts[0]["forecast_date"],
        "fetched_at": forecasts[0]["fetched_at"],
        "rainfall_effectiveness": rainfall_effectiveness,
        "source": forecasts[0]["source"], "weather_live": True, "demo": True,
        "method": "Area-weighted estimate from up to 9 samples in a clipped 3 by 3 grid. Nearby samples may use the same weather grid cell. One crop and growth stage apply to the entire field.",
    }
