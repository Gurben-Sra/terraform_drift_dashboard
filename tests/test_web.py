import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from terraform_drift_dashboard.models import DriftResult
from terraform_drift_dashboard.web import create_server


class FakeInspector:
    def inspect(self, expectations: list) -> list[DriftResult]:
        self.expectations = expectations
        return [
            DriftResult(
                address="aws_instance.app",
                instance_id="i-123",
                expected="t3.medium",
                actual="t3.large",
                status="DRIFTED",
            )
        ]


class DashboardServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "terraform.tfstate"
        self.state_path.write_text(
            json.dumps(
                {
                    "resources": [
                        {
                            "mode": "managed",
                            "type": "aws_instance",
                            "name": "app",
                            "instances": [
                                {
                                    "attributes": {
                                        "id": "i-123",
                                        "instance_type": "t3.medium",
                                    }
                                }
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.inspector = FakeInspector()
        self.server = create_server(
            state_path=self.state_path,
            port=0,
            inspector_factory=lambda region, profile: self.inspector,
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp_dir.cleanup()

    def request(self, method: str, path: str, headers: dict[str, str] | None = None):
        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, response.getheader("Content-Type"), body

    def test_serves_dashboard_and_health_check(self) -> None:
        status, content_type, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Run scan", body)

        status, _, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ready", "resource_type": "aws_instance"})

    def test_scan_returns_live_results_in_ui_response_shape(self) -> None:
        status, content_type, body = self.request(
            "POST",
            "/api/scan",
            headers={"Origin": f"http://127.0.0.1:{self.port}"},
        )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(
            payload["results"][0],
            {
                "address": "aws_instance.app",
                "instance_id": "i-123",
                "expected": "t3.medium",
                "actual": "t3.large",
                "status": "DRIFTED",
            },
        )
        self.assertEqual(self.inspector.expectations[0].instance_id, "i-123")

    def test_rejects_cross_origin_scan_requests(self) -> None:
        status, _, body = self.request(
            "POST",
            "/api/scan",
            headers={"Origin": "http://attacker.example"},
        )

        self.assertEqual(status, 403)
        self.assertIn("Cross-origin", json.loads(body)["error"])

    def test_missing_state_is_reported_as_client_error(self) -> None:
        self.state_path.unlink()
        status, _, body = self.request("POST", "/api/scan")

        self.assertEqual(status, 400)
        self.assertIn("Unable to read Terraform state", json.loads(body)["error"])
        self.assertFalse(hasattr(self.inspector, "expectations"))


if __name__ == "__main__":
    unittest.main()
