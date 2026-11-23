import unittest

from fastapi.testclient import TestClient

from app.main import app


class CORSMiddlewareTests(unittest.TestCase):
    def test_local_frontend_can_make_authenticated_api_requests(self):
        with TestClient(app) as client:
            response = client.options(
                "/vehicles/",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertIn(
            "authorization",
            response.headers["access-control-allow-headers"].lower(),
        )
