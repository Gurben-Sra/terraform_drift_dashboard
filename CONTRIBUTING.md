# Contributing

Thanks for helping improve Terraform Drift Dashboard.

## Before opening a change

1. Keep changes focused and update the README when behavior or usage changes.
2. Add or update tests for behavior changes.
3. Run `python -m unittest discover -s tests -v`.
4. Do not commit Terraform state files, AWS credentials, `.env` files, or
   generated reports containing infrastructure details.

## Pull requests

Describe the user-visible change, how it was tested, and any AWS permissions or
Terraform state assumptions it introduces. Do not include production state
snapshots or credentials in pull requests.
