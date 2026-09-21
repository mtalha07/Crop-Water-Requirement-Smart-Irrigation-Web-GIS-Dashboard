import json
from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse
from pyproj import Geod
from shapely.geometry import Point, Polygon
from backend.api.polygon_water import prepare_polygon_samples, calculate_polygon_water
from backend.api.open_meteo_api import WeatherDataError

FIELD = {"type": "Polygon", "coordinates": [[
    [74.35, 31.63], [74.36, 31.63], [74.36, 31.64], [74.35, 31.64], [74.35, 31.63]
]]}


def forecast(et=5, rain=0):
    return {"evapotranspiration": et, "rainfall": rain, "forecast_date": "2026-09-21",
            "timezone": "Asia/Karachi", "fetched_at": "2026-09-21T12:00:00Z",
            "source": "Test forecast", "weather_live": True}


class PolygonTests(SimpleTestCase):
    def test_geodesic_area_and_reversed_boundary(self):
        area, samples = prepare_polygon_samples(FIELD)
        expected = abs(Geod(ellps="WGS84").polygon_area_perimeter(
            [p[0] for p in FIELD["coordinates"][0]], [p[1] for p in FIELD["coordinates"][0]])[0])
        self.assertAlmostEqual(area, expected)
        self.assertAlmostEqual(sum(s["area_m2"] for s in samples), area)
        self.assertEqual(len(samples), 9)
        reverse_field = {"type": "Polygon", "coordinates": [FIELD["coordinates"][0][::-1]]}
        self.assertAlmostEqual(prepare_polygon_samples(reverse_field)[0], area, places=4)

    def test_concave_polygon_has_samples_inside_and_area_is_conserved(self):
        concave = {"type": "Polygon", "coordinates": [[
            [74.35, 31.63], [74.36, 31.63], [74.36, 31.633],
            [74.353, 31.633], [74.353, 31.64], [74.35, 31.64], [74.35, 31.63]
        ]]}
        area, samples = prepare_polygon_samples(concave)
        self.assertAlmostEqual(sum(s["area_m2"] for s in samples), area)
        self.assertTrue(1 <= len(samples) <= 9)
        shape = Polygon(concave["coordinates"][0])
        for sample in samples:
            self.assertTrue(shape.contains(Point(sample["longitude"], sample["latitude"])))

    @patch("backend.api.polygon_water.fetch_weather_for_locations")
    def test_constant_weather_volume_matches_point_depth_times_area(self, weather):
        weather.side_effect = lambda locations: [forecast() for _ in locations]
        result = calculate_polygon_water("wheat", "mid", FIELD, 80)
        self.assertEqual(result["required_water"], 5.75)
        self.assertAlmostEqual(result["total_water_litres"], result["area_m2"] * 5.75, places=2)
        self.assertAlmostEqual(result["total_water_m3"], result["total_water_litres"] / 1000, places=3)
        self.assertEqual(weather.call_count, 1)

    @patch("backend.api.polygon_water.prepare_polygon_samples")
    @patch("backend.api.polygon_water.fetch_weather_for_locations")
    def test_varied_weather_is_weighted_and_wet_cell_does_not_cancel_dry_cell(self, weather, prepare):
        prepare.return_value = (10000, [
            {"latitude": 31.63, "longitude": 74.35, "area_m2": 2500},
            {"latitude": 31.64, "longitude": 74.36, "area_m2": 7500},
        ])
        weather.return_value = [forecast(10), forecast(1, 10)]
        result = calculate_polygon_water("wheat", "mid", FIELD, 80)
        self.assertEqual(result["total_water_litres"], 28750)
        self.assertEqual(result["required_water"], 2.88)
        self.assertEqual(result["samples"][1]["required_water"], 0)

    @patch("backend.api.polygon_water.fetch_weather_for_locations")
    def test_bad_boundary_rejected_before_weather_request(self, weather):
        bad_fields = [None, {}, {"type": "Point", "coordinates": [74, 31]},
            {"type": "Polygon", "coordinates": []},
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
            {"type": "Polygon", "coordinates": [[[0, 0], [0, 0], [0, 0], [0, 0]]]},
            {"type": "Polygon", "coordinates": [[[181, 31], [74, 31], [74, 32], [181, 31]]]},
            {"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 1], [0, 0]]]},
            {"type": "Polygon", "coordinates": [[[74, 31], [74.1, 31], [74.1, 31.1], [74, 31.1]]]},
        ]
        for field in bad_fields:
            with self.subTest(field=field), self.assertRaises(ValueError):
                calculate_polygon_water("wheat", "mid", field, 80)
        weather.assert_not_called()

    @patch("backend.api.polygon_water.fetch_weather_for_locations")
    def test_polygon_endpoint_and_weather_failure(self, weather):
        payload = {"crop": "wheat", "stage": "mid", "mode": "polygon", "polygon": json.dumps(FIELD)}
        weather.side_effect = lambda locations: [forecast() for _ in locations]
        response = self.client.post(reverse("required_water"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "polygon")
        self.assertGreater(response.json()["total_water_litres"], 0)
        weather.side_effect = WeatherDataError("Weather unavailable")
        self.assertEqual(self.client.post(reverse("required_water"), payload).status_code, 503)
        self.assertEqual(self.client.post(reverse("required_water"), {**payload, "polygon": "bad json"}).status_code, 400)

    @patch("backend.api.polygon_water.fetch_weather_for_locations")
    def test_mixed_forecast_dates_are_rejected(self, weather):
        def mixed(locations):
            rows = [forecast() for _ in locations]
            rows[-1]["forecast_date"] = "2026-09-22"
            return rows
        weather.side_effect = mixed
        with self.assertRaises(WeatherDataError):
            calculate_polygon_water("wheat", "mid", FIELD, 80)
