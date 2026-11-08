from contextlib import redirect_stderr
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terraform_drift_dashboard.cli import main
from terraform_drift_dashboard.models import DriftResult


class CliTests(unittest.TestCase):
    def test_fail_on_drift_writes_report_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "terraform.tfstate"
            state_path.write_text('{"resources": []}', encoding="utf-8")
            output_path = Path(directory) / "report.md"
            results = [
                DriftResult(
                    address="aws_instance.app",
                    instance_id="i-123",
                    expected="t3.medium",
                    actual="t3.large",
                    status="DRIFTED",
                )
            ]
            with patch("terraform_drift_dashboard.cli.Ec2Inspector") as inspector:
                inspector.return_value.inspect.return_value = results
                exit_code = main(
                    [
                        "--state",
                        str(state_path),
                        "--output-file",
                        str(output_path),
                        "--fail-on-drift",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("t3.medium | t3.large | DRIFTED", output_path.read_text(encoding="utf-8"))

    def test_state_errors_return_two_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.tfstate"
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(["--state", str(missing_path)])

        self.assertEqual(exit_code, 2)
        self.assertIn("terraform-drift-dashboard: Unable to read Terraform state file", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
