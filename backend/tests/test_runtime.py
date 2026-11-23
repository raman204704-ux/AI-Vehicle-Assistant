import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.main import app


class RuntimeBehaviorTests(unittest.TestCase):
    def test_request_log_is_structured_without_query_parameters(self):
        with self.assertLogs("app.main", level="INFO") as captured:
            with TestClient(app) as client:
                response = client.get(
                    "/health?token=must-not-be-logged",
                    headers={"X-Request-ID": "request-456"},
                )

        request_events = [
            json.loads(record.getMessage())
            for record in captured.records
            if '"event":"http_request_completed"' in record.getMessage()
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request_events), 1)
        self.assertEqual(request_events[0]["request_id"], "request-456")
        self.assertEqual(request_events[0]["path"], "/health")
        self.assertEqual(request_events[0]["status_code"], 200)
        self.assertNotIn("must-not-be-logged", captured.output[0])

    def test_health_endpoint_echoes_only_safe_request_ids(self):
        with TestClient(app) as client:
            response = client.get(
                "/health",
                headers={"X-Request-ID": "safe.request-123"},
            )
            generated_response = client.get(
                "/health",
                headers={"X-Request-ID": "contains spaces"},
            )

        self.assertEqual(response.headers["x-request-id"], "safe.request-123")
        self.assertNotEqual(
            generated_response.headers["x-request-id"],
            "contains spaces",
        )
        self.assertEqual(generated_response.status_code, 200)

    def test_readiness_returns_dependency_status_without_internal_details(self):
        with (
            patch("app.main._database_is_ready", return_value=False),
            patch("app.main._redis_is_ready", return_value=True),
            TestClient(app) as client,
        ):
            response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "status": "not_ready",
                "checks": {
                    "database": "unavailable",
                    "redis": "ok",
                },
            },
        )

    def test_readiness_dependency_failures_do_not_return_exception_text(self):
        with (
            patch("app.main.engine.connect", side_effect=SQLAlchemyError("db-secret")),
            patch(
                "app.main.Redis.from_url",
                side_effect=RedisError("redis-secret"),
            ),
        ):
            response = TestClient(app).get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("db-secret", response.text)
        self.assertNotIn("redis-secret", response.text)

    def test_validation_errors_do_not_echo_submitted_values(self):
        with TestClient(app) as client:
            response = client.post(
                "/auth/register",
                json={
                    "email": "not-an-email",
                    "password": "SuperSecret123!",
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("SuperSecret123!", response.text)
        self.assertNotIn('"input"', response.text)
        self.assertIn("detail", response.json())

    def test_production_configuration_requires_https_and_postgresql(self):
        config = Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg2://user:pass@db/vehicle_maintenance",
            secret_key=SecretStr("x" * 40),
            cors_origins="http://localhost:5173",
        )

        with self.assertRaisesRegex(ValueError, "HTTPS origins"):
            config.validate_runtime_configuration()

        config.cors_origins = "https://app.example.com"
        config.validate_runtime_configuration()

        config.database_url = "sqlite:///./vehicle_maintenance.db"
        with self.assertRaisesRegex(ValueError, "PostgreSQL"):
            config.validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
