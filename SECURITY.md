# Security

Please do not report security issues publicly. Contact the repository
maintainers privately with a description and steps to reproduce.

Terraform state may contain secrets and infrastructure identifiers. Keep state
snapshots out of source control, restrict access to generated reports, and use
short-lived AWS credentials with only the permissions the checker needs.

The tool is designed to make read-only AWS API calls. It does not apply
Terraform changes or modify AWS resources.
