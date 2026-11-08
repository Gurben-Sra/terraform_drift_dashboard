"""Render drift results as Markdown or JSON."""

import json
from dataclasses import asdict
from typing import Literal

from terraform_drift_dashboard.models import DriftResult


def render_json(results: list[DriftResult]) -> str:
    """Render a machine-readable JSON report."""
    return json.dumps([asdict(result) for result in results], indent=2)


def _markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_markdown(results: list[DriftResult]) -> str:
    """Render a human-readable Markdown report."""
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("IN_SYNC", "DRIFTED", "MISSING")
    }
    lines = [
        "# Terraform Drift Report",
        "",
        f"Checked **{len(results)}** resource(s): {counts['IN_SYNC']} in sync, "
        f"{counts['DRIFTED']} drifted, {counts['MISSING']} missing.",
        "",
        "| Resource | Instance ID | Expected | Actual | Status |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        actual = result.actual if result.actual is not None else "Not found"
        values = (
            result.address,
            result.instance_id,
            result.expected,
            actual,
            result.status,
        )
        lines.append("| " + " | ".join(_markdown_cell(value) for value in values) + " |")
    if not results:
        lines.append("| - | - | - | - | - |")
    return "\n".join(lines)


def render_report(results: list[DriftResult], output_format: Literal["markdown", "json"]) -> str:
    """Render the report using the selected output format."""
    if output_format == "json":
        return render_json(results)
    return render_markdown(results)
