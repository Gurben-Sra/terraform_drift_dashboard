"""Read live EC2 instance types using boto3."""

from collections.abc import Iterable
from typing import Any

from terraform_drift_dashboard.models import DriftResult, InstanceExpectation


class AwsLookupError(RuntimeError):
    """Raised when the live AWS configuration cannot be read."""


class Ec2Inspector:
    """Read EC2 instance types without changing AWS resources."""

    def __init__(
        self,
        region: str | None = None,
        profile: str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is None:
            try:
                import boto3
                from botocore.exceptions import BotoCoreError, ClientError
            except ImportError as error:
                raise AwsLookupError(
                    "boto3 is required for AWS scans. Install the project dependencies with "
                    "'python -m pip install -e .'."
                ) from error

            self._sdk_errors: tuple[type[BaseException], ...] = (BotoCoreError, ClientError)
            self._client_error = ClientError
            try:
                session = boto3.Session(profile_name=profile, region_name=region)
                client = session.client("ec2")
            except self._sdk_errors as error:
                raise AwsLookupError(f"Unable to create AWS EC2 client: {error}") from error
        else:
            self._sdk_errors = ()
            self._client_error = None
        self._client = client

    def _fetch_instance_types(self, instance_ids: list[str]) -> dict[str, str]:
        instance_types: dict[str, str] = {}

        def fetch_batch(batch: list[str]) -> None:
            try:
                response = self._client.describe_instances(InstanceIds=batch)
            except self._sdk_errors as error:
                if not (
                    self._client_error is not None
                    and isinstance(error, self._client_error)
                    and error.response.get("Error", {}).get("Code")
                    == "InvalidInstanceID.NotFound"
                ):
                    raise AwsLookupError(f"AWS DescribeInstances failed: {error}") from error
                if len(batch) > 1:
                    for instance_id in batch:
                        fetch_batch([instance_id])
                return

            reservations = response.get("Reservations")
            if not isinstance(reservations, list):
                raise AwsLookupError("AWS DescribeInstances returned an invalid response.")
            for reservation in reservations:
                if not isinstance(reservation, dict) or not isinstance(
                    reservation.get("Instances"), list
                ):
                    raise AwsLookupError("AWS DescribeInstances returned an invalid reservation.")
                for instance in reservation["Instances"]:
                    if not isinstance(instance, dict):
                        raise AwsLookupError("AWS DescribeInstances returned an invalid instance.")
                    instance_id = instance.get("InstanceId")
                    instance_type = instance.get("InstanceType")
                    if not isinstance(instance_id, str) or not isinstance(instance_type, str):
                        raise AwsLookupError(
                            "AWS DescribeInstances returned an instance without its ID or type."
                        )
                    instance_types[instance_id] = instance_type

        for offset in range(0, len(instance_ids), 1000):
            batch = instance_ids[offset : offset + 1000]
            fetch_batch(batch)
        return instance_types

    def inspect(self, expectations: Iterable[InstanceExpectation]) -> list[DriftResult]:
        """Compare expected types with live values for the supplied state objects."""
        expected = list(expectations)
        live_types = self._fetch_instance_types(
            list(dict.fromkeys(item.instance_id for item in expected))
        )

        results: list[DriftResult] = []
        for item in expected:
            actual = live_types.get(item.instance_id)
            status = (
                "MISSING"
                if actual is None
                else "IN_SYNC"
                if actual == item.expected_instance_type
                else "DRIFTED"
            )
            results.append(
                DriftResult(
                    address=item.address,
                    instance_id=item.instance_id,
                    expected=item.expected_instance_type,
                    actual=actual,
                    status=status,
                )
            )
        return results
