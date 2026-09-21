from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch
from backend.api.open_meteo_api import WeatherDataError
from .models import Pole


class LocalDemoTests(TestCase):
    fixtures = ["demo_poles"]

    def setUp(self):
        weather_patch = patch("backend.api.crop_water_requirement.fetch_soil_and_weather_data")
        self.weather = weather_patch.start()
        self.addCleanup(weather_patch.stop)
        self.weather.return_value = {
            "evapotranspiration": 5.0, "rainfall": 1.25,
            "forecast_date": "2026-09-21", "timezone": "Asia/Karachi",
            "fetched_at": "2026-09-21T10:00:00+00:00",
            "source": "Open-Meteo daily forecast", "weather_live": True,
        }

    def test_dashboard_renders_form_and_csrf(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "Live weather forecast")
        self.assertContains(response, 'name="rainfall_effectiveness"')
        self.assertContains(response, reverse("required_water"))
        self.assertContains(response, reverse("fetch_spatial_data"))

    def test_sqlite_points_are_returned(self):
        response = self.client.get(reverse("fetch_spatial_data"))
        self.assertEqual(response.status_code, 200)
        points = response.json()["poles"]
        self.assertEqual(len(points), 5)
        self.assertEqual(points[0]["PoleSurveyNumber"], "DEMO-001")
        self.assertEqual(points[0]["latitude"], 31.63)

    def test_empty_points_response(self):
        Pole.objects.all().delete()
        self.assertEqual(self.client.get(reverse("fetch_spatial_data")).json()["poles"], [])

    def test_forecast_calculation_depends_on_crop_stage(self):
        payload = {"crop": "wheat", "stage": "initial", "lat": "31.63", "lon": "74.35"}
        first = self.client.post(reverse("required_water"), payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["required_water"], 0.5)
        payload["stage"] = "mid"
        second = self.client.post(reverse("required_water"), payload)
        self.assertEqual(second.json()["required_water"], 4.75)
        self.assertTrue(second.json()["demo"])
        self.assertTrue(second.json()["weather_live"])
        self.weather.assert_called_with(31.63, 74.35)

    def test_rainfall_assumption_changes_result_and_result_never_negative(self):
        payload = {"crop": "wheat", "stage": "mid", "lat": "31.63", "lon": "74.35"}
        for effectiveness, expected in [(0, 5.75), (40, 5.25), (100, 4.5)]:
            response = self.client.post(reverse("required_water"), {
                **payload, "rainfall_effectiveness": effectiveness,
            })
            self.assertEqual(response.json()["required_water"], expected)
        self.weather.return_value["rainfall"] = 100
        self.assertEqual(self.client.post(reverse("required_water"), payload).json()["required_water"], 0)

    def test_weather_failure_returns_503_without_fake_result(self):
        self.weather.side_effect = WeatherDataError("Weather unavailable")
        response = self.client.post(reverse("required_water"), {
            "crop": "wheat", "stage": "mid", "lat": "31.63", "lon": "74.35",
        })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "Weather unavailable"})

    def test_invalid_input_returns_400(self):
        valid = {"crop": "wheat", "stage": "mid", "lat": "31.63", "lon": "74.35"}
        for changes in [
            {"lat": ""}, {"lat": "nan"}, {"lon": "inf"},
            {"lat": "91"}, {"lon": "-181"},
            {"crop": "unknown"}, {"stage": "unknown"},
            {"rainfall_effectiveness": "nan"}, {"rainfall_effectiveness": "101"},
            {"rainfall_effectiveness": "-1"}, {"rainfall_effectiveness": ""},
        ]:
            with self.subTest(changes=changes):
                response = self.client.post(reverse("required_water"), {**valid, **changes})
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json())
        self.weather.assert_not_called()

    def test_calculation_requires_post(self):
        self.assertEqual(self.client.get(reverse("required_water")).status_code, 405)

    def test_csrf_is_required_and_valid_token_works(self):
        client = Client(enforce_csrf_checks=True)
        payload = {"crop": "wheat", "stage": "mid", "lat": "31.63", "lon": "74.35"}
        url = reverse("required_water")
        self.assertEqual(client.post(url, payload).status_code, 403)
        client.get(reverse("dashboard"))
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, payload, HTTP_X_CSRFTOKEN=token).status_code, 200)
