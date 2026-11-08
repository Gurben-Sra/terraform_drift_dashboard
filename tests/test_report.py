import json
import unittest

from terraform_drift_dashboard.models import DriftResult
from terraform_drift_dashboard.report import render_json, render_markdown, render_report


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results = [
            DriftResult(
                address="aws_instance.app",
                instance_id="i-123",
                expected="t3.medium",
                actual="t3.large",
                status="DRIFTED",
            ),
            DriftResult(
                address="aws_instance.old",
                instance_id="i-456",
                expected="t3.small",
                actual=None,
                status="MISSING",
            ),
        ]

    def test_markdown_includes_values_and_summary(self) -> None:
        report = render_markdown(self.results)

        self.assertIn("0 in sync, 1 drifted, 1 missing", report)
        self.assertIn("| aws_instance.app | i-123 | t3.medium | t3.large | DRIFTED |", report)
        self.assertIn("| aws_instance.old | i-456 | t3.small | Not found | MISSING |", report)

    def test_json_is_parseable_and_preserves_null_actual_value(self) -> None:
        decoded = json.loads(render_json(self.results))

        self.assertEqual(decoded[0]["status"], "DRIFTED")
        self.assertIsNone(decoded[1]["actual"])

    def test_empty_markdown_report_is_well_formed(self) -> None:
        report = render_report([], "markdown")

        self.assertIn("Checked **0** resource(s)", report)
        self.assertIn("| - | - | - | - | - |", report)


if __name__ == "__main__":
    unittest.main()
