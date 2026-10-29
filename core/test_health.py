from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_health_reports_database_available(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("core.views.connection.cursor", side_effect=OperationalError("database unavailable"))
    def test_health_returns_503_when_database_is_unavailable(self, mocked_cursor):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unhealthy", "database": "unavailable"},
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        mocked_cursor.assert_called_once_with()

    def test_health_is_get_only(self):
        response = self.client.post(reverse("health"))
        self.assertEqual(response.status_code, 405)
