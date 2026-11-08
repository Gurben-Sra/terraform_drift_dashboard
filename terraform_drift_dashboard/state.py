"""Read EC2 instance expectations from Terraform state JSON."""

import json
from pathlib import Path
from typing import Any

from terraform_drift_dashboard.models import InstanceExpectation


class StateFileError(ValueError):
    """Raised when a Terraform state file cannot be interpreted."""


def _resource_address(resource: dict[str, Any], index_key: Any = None) -> str:
    parts = [resource["type"], resource["name"]]
    module = resource.get("module")
    address = f"{module}.{'.'.join(parts)}" if module else ".".join(parts)
    if isinstance(index_key, int) and not isinstance(index_key, bool):
        return f"{address}[{index_key}]"
    if isinstance(index_key, str):
        return f"{address}[{json.dumps(index_key)}]"
    return address


def load_instance_expectations(path: Path) -> list[InstanceExpectation]:
    """Load managed aws_instance objects and their expected instance types."""
    try:
        with path.open(encoding="utf-8") as state_file:
            state = json.load(state_file)
    except OSError as error:
        raise StateFileError(f"Unable to read Terraform state file '{path}': {error}") from error
    except json.JSONDecodeError as error:
        raise StateFileError(f"Terraform state file '{path}' is not valid JSON: {error}") from error

    if not isinstance(state, dict) or not isinstance(state.get("resources"), list):
        raise StateFileError("Terraform state must be a JSON object with a resources list.")

    expectations: list[InstanceExpectation] = []
    for resource in state["resources"]:
        if not isinstance(resource, dict):
            raise StateFileError("Terraform state contains a resource entry that is not an object.")
        if resource.get("mode", "managed") != "managed" or resource.get("type") != "aws_instance":
            continue

        if not isinstance(resource.get("name"), str) or not isinstance(resource.get("instances"), list):
            raise StateFileError("An aws_instance resource is missing its name or instances list.")

        for instance in resource["instances"]:
            if not isinstance(instance, dict) or not isinstance(instance.get("attributes"), dict):
                raise StateFileError(f"Resource '{resource['name']}' has an invalid instance entry.")

            attributes = instance["attributes"]
            instance_id = attributes.get("id")
            instance_type = attributes.get("instance_type")
            if not isinstance(instance_id, str) or not instance_id:
                raise StateFileError(f"Resource '{resource['name']}' has no valid instance ID.")
            if not isinstance(instance_type, str) or not instance_type:
                raise StateFileError(
                    f"Resource '{resource['name']}' has no valid expected instance type."
                )

            expectations.append(
                InstanceExpectation(
                    address=_resource_address(resource, instance.get("index_key")),
                    instance_id=instance_id,
                    expected_instance_type=instance_type,
                )
            )

    return expectations
