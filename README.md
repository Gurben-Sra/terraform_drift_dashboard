# Terraform Drift Dashboard

Terraform Drift Dashboard compares selected values in a local Terraform state
snapshot with live AWS resources and creates a report. The initial MVP supports
the `aws_instance` resource's `instance_type` attribute.

## Why

Terraform state may say an EC2 instance is `t3.medium` while the live instance
has been manually changed to `t3.large`. This tool flags that mismatch before
it surprises a deployment or operations team.

## What it does

- Reads managed `aws_instance` resources from a Terraform state JSON file.
- Queries EC2 using the AWS SDK's normal credential chain.
- Reports `IN_SYNC`, `DRIFTED`, or `MISSING` instances as Markdown or JSON.
- Can return a non-zero exit status when drift is found, for CI use.

Example:

| Resource | Instance ID | Expected | Actual | Status |
|---|---|---|---|---|
| `aws_instance.app` | `i-0123456789abcdef0` | `t3.medium` | `t3.large` | `DRIFTED` |

The MVP checks instance type only. It does not modify AWS or Terraform state,
support other resource types, or create GitHub issues, Slack messages, or Jira
tickets. A `MISSING` result means the instance ID was not returned in the
selected AWS account and region; verify both before concluding the instance was
deleted.

## Requirements

- Python 3.10 or newer
- AWS credentials configured through an AWS profile, environment variables, or
  another [boto3 credential provider](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- Permission to call `ec2:DescribeInstances` in the account being checked

## Install

From a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Use

Export a state snapshot from the Terraform working directory. Treat this file
as sensitive: Terraform state can contain secrets.

```bash
terraform state pull > terraform.tfstate
```

Generate a Markdown report:

```bash
terraform-drift-dashboard \
  --state terraform.tfstate \
  --region us-east-1 \
  --output markdown \
  --output-file drift-report.md
```

Use a named AWS profile with `--profile production`. To emit JSON to standard
output instead:

```bash
terraform-drift-dashboard --state terraform.tfstate --region us-east-1 --output json
```

For CI, `--fail-on-drift` exits with status `1` when at least one instance is
drifted or missing. Configuration and AWS errors are written to standard error
and also exit non-zero.

Run `terraform-drift-dashboard --help` for all options.

## AWS access

Use credentials for the same account and region in which the Terraform
resources exist. The tool only needs the read-only `ec2:DescribeInstances`
action. For example, an IAM policy can grant that action with `"Resource": "*"`
because EC2 does not support resource-level permissions for this operation.
Prefer temporary credentials or an assumed role over long-lived access keys.

## Development

Run the test suite with the Python standard library:

```bash
python -m unittest discover -s tests -v
```

Tests use a fake EC2 client and do not require AWS credentials or network access.

## Project status

This is an early MVP, not a continuously running dashboard. It reads a state
snapshot on demand. Future work could add more resource types, scheduled checks,
and optional issue or notification integrations.
