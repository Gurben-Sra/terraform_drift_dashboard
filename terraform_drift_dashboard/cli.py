"""Command-line entry point."""

import argparse
import sys
from pathlib import Path

from terraform_drift_dashboard.aws import AwsLookupError, Ec2Inspector
from terraform_drift_dashboard.report import render_report
from terraform_drift_dashboard.state import StateFileError, load_instance_expectations


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Terraform aws_instance state with live EC2 instance types."
    )
    parser.add_argument("--state", type=Path, default=Path("terraform.tfstate"))
    parser.add_argument("--region", help="AWS region (otherwise use the AWS SDK configuration).")
    parser.add_argument("--profile", help="AWS shared-config profile to use.")
    parser.add_argument(
        "--output",
        choices=("markdown", "json"),
        default="markdown",
        help="Report format (default: markdown).",
    )
    parser.add_argument("--output-file", type=Path, help="Write the report to this file.")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit with status 1 when any resource is drifted or missing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        expectations = load_instance_expectations(args.state)
        results = Ec2Inspector(region=args.region, profile=args.profile).inspect(expectations)
    except (StateFileError, AwsLookupError) as error:
        print(f"terraform-drift-dashboard: {error}", file=sys.stderr)
        return 2

    report = render_report(results, args.output)
    if args.output_file is None:
        print(report)
    else:
        try:
            args.output_file.write_text(report + "\n", encoding="utf-8")
        except OSError as error:
            print(f"terraform-drift-dashboard: unable to write report: {error}", file=sys.stderr)
            return 2

    if args.fail_on_drift and any(result.status != "IN_SYNC" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
