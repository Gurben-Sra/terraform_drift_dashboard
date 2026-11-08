"""Local web dashboard for on-demand Terraform drift scans."""

import argparse
import json
import logging
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from terraform_drift_dashboard.aws import AwsLookupError, Ec2Inspector
from terraform_drift_dashboard.models import DriftResult, InstanceExpectation
from terraform_drift_dashboard.state import StateFileError, load_instance_expectations


LOGGER = logging.getLogger(__name__)
_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Inspector(Protocol):
    def inspect(self, expectations: list[InstanceExpectation]) -> list[DriftResult]: ...


InspectorFactory = Callable[[str | None, str | None], Inspector]


def create_server(
    state_path: Path,
    region: str | None = None,
    profile: str | None = None,
    port: int = 8765,
    inspector_factory: InspectorFactory | None = None,
) -> ThreadingHTTPServer:
    """Create a loopback-only server for the dashboard and scan endpoint."""
    factory = inspector_factory or (
        lambda selected_region, selected_profile: Ec2Inspector(
            region=selected_region,
            profile=selected_profile,
        )
    )
    dashboard_html = files("demo").joinpath("index.html").read_bytes()

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "TerraformDriftDashboard"

        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(payload).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _is_local_host(self) -> bool:
            host_header = self.headers.get("Host", "")
            host = urlsplit(f"//{host_header}").hostname
            return host is not None and host.lower() in _ALLOWED_HOSTS

        def do_GET(self) -> None:
            if not self._is_local_host():
                self._send_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": "Only local dashboard access is allowed."},
                )
                return

            path = urlsplit(self.path).path
            if path in {"/", "/demo", "/demo/"}:
                self._send(HTTPStatus.OK, dashboard_html, "text/html; charset=utf-8")
            elif path == "/api/health":
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ready", "resource_type": "aws_instance"},
                )
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

        def do_POST(self) -> None:
            if not self._is_local_host():
                self._send_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": "Only local dashboard access is allowed."},
                )
                return

            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "").lower()
            if origin is not None:
                parsed_origin = urlsplit(origin)
                if parsed_origin.scheme != "http" or parsed_origin.netloc.lower() != host:
                    self._send_json(
                        HTTPStatus.FORBIDDEN,
                        {"error": "Cross-origin requests are not allowed."},
                    )
                    return

            if self.path != "/api/scan":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return

            content_length = self.headers.get("Content-Length", "0")
            if self.headers.get("Transfer-Encoding") or content_length != "0":
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "The scan endpoint does not accept a request body."},
                )
                return

            try:
                expectations = load_instance_expectations(state_path)
                results = factory(region, profile).inspect(expectations)
            except StateFileError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except AwsLookupError as error:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})
                return

            self._send_json(
                HTTPStatus.OK,
                {
                    "count": len(results),
                    "results": [
                        {
                            "address": result.address,
                            "instance_id": result.instance_id,
                            "expected": result.expected,
                            "actual": result.actual,
                            "status": result.status,
                        }
                        for result in results
                    ],
                },
            )

        def log_message(self, format_string: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format_string % args)

    class LocalDashboardServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    return LocalDashboardServer(("127.0.0.1", port), DashboardHandler)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be a number between 1 and 65535") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be a number between 1 and 65535")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the local Terraform Drift Dashboard."
    )
    parser.add_argument("--state", type=Path, default=Path("terraform.tfstate"))
    parser.add_argument("--region", help="AWS region (otherwise use the AWS SDK configuration).")
    parser.add_argument("--profile", help="AWS shared-config profile to use.")
    parser.add_argument("--port", type=_port, default=8765, help="Local web port (default: 8765).")
    args = parser.parse_args(argv)

    try:
        server = create_server(
            state_path=args.state,
            region=args.region,
            profile=args.profile,
            port=args.port,
        )
    except OSError as error:
        parser.exit(2, f"terraform-drift-dashboard-web: unable to start local server: {error}\n")

    print(
        f"Terraform Drift Dashboard listening at http://127.0.0.1:{args.port}/ "
        f"(state: {args.state})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Terraform Drift Dashboard.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
