import copy
import io
import json
import ssl
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from backend.api.open_meteo_api import WeatherDataError, fetch_soil_and_weather_data, fetch_weather_for_locations


class OpenMeteoTests(TestCase):
    def setUp(self):
        self.payload = {
            "timezone": "Asia/Karachi",
            "daily_units": {
                "et0_fao_evapotranspiration": "mm", "rain_sum": "mm", "showers_sum": "mm",
            },
            "daily": {
                "time": ["2026-09-21"], "et0_fao_evapotranspiration": [4.6],
                "rain_sum": [1.0], "showers_sum": [0.5],
            },
        }

    def response(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    @patch("backend.api.open_meteo_api.urlopen")
    def test_coordinates_daily_units_and_rain_mapping(self, open_url):
        open_url.return_value = self.response(self.payload)
        result = fetch_soil_and_weather_data(31.63, 74.35)
        self.assertEqual(result["evapotranspiration"], 4.6)
        self.assertEqual(result["rainfall"], 1.5)
        self.assertEqual(result["forecast_date"], "2026-09-21")
        self.assertEqual(result["timezone"], "Asia/Karachi")
        self.assertTrue(result["weather_live"])
        self.assertNotIn("effective_rainfall", result)
        request = open_url.call_args.args[0]
        params = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(params["latitude"], ["31.63"])
        self.assertEqual(params["longitude"], ["74.35"])
        self.assertEqual(params["forecast_days"], ["1"])
        self.assertEqual(params["timezone"], ["auto"])
        self.assertEqual(open_url.call_args.kwargs["timeout"], 10)
        context = open_url.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    @patch("backend.api.open_meteo_api.urlopen")
    def test_batch_weather_uses_every_location_and_checks_count(self, open_url):
        other = copy.deepcopy(self.payload)
        other["daily"]["et0_fao_evapotranspiration"] = [6]
        open_url.return_value = self.response([self.payload, other])
        result = fetch_weather_for_locations([(31.63, 74.35), (31.64, 74.36)])
        self.assertEqual([r["evapotranspiration"] for r in result], [4.6, 6])
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["latitude"], ["31.63,31.64"])
        open_url.return_value = self.response([self.payload])
        with self.assertRaises(WeatherDataError):
            fetch_weather_for_locations([(31.63, 74.35), (31.64, 74.36)])

    @patch("backend.api.open_meteo_api.urlopen")
    def test_network_and_rate_limit_failures(self, open_url):
        for error in [URLError("offline"), TimeoutError(), HTTPError("https://example.org", 429, "Too many requests", {}, None)]:
            with self.subTest(error=type(error).__name__):
                open_url.side_effect = error
                with self.assertRaises(WeatherDataError):
                    fetch_soil_and_weather_data(31.63, 74.35)

    @patch("backend.api.open_meteo_api.urlopen")
    def test_missing_invalid_and_null_weather_is_rejected(self, open_url):
        for value in [None, -1, "5", True, float("nan"), float("inf")]:
            payload = copy.deepcopy(self.payload)
            payload["daily"]["et0_fao_evapotranspiration"] = [value]
            open_url.return_value = self.response(payload)
            with self.subTest(value=value), self.assertRaises(WeatherDataError):
                fetch_soil_and_weather_data(31.63, 74.35)
        for payload in [{}, [], {"error": True}, {**self.payload, "daily": {}},
                        {**self.payload, "daily_units": {"rain_sum": "inch"}}]:
            open_url.return_value = self.response(payload)
            with self.assertRaises(WeatherDataError):
                fetch_soil_and_weather_data(31.63, 74.35)
        open_url.return_value = io.BytesIO(b"not json")
        with self.assertRaises(WeatherDataError):
            fetch_soil_and_weather_data(31.63, 74.35)
