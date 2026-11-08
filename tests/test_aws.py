import unittest

from terraform_drift_dashboard.aws import Ec2Inspector
from terraform_drift_dashboard.models import InstanceExpectation


class FakeEc2Client:
    def __init__(self, instances: dict[str, str]) -> None:
        self.instances = instances
        self.requested_ids: list[str] = []

    def describe_instances(self, InstanceIds: list[str]) -> dict:
        self.requested_ids.extend(InstanceIds)
        found = [
            {"InstanceId": instance_id, "InstanceType": self.instances[instance_id]}
            for instance_id in InstanceIds
            if instance_id in self.instances
        ]
        return {"Reservations": [{"Instances": found}]}


class Ec2InspectorTests(unittest.TestCase):
    def test_reports_in_sync_drifted_and_missing_instances(self) -> None:
        client = FakeEc2Client({"i-sync": "t3.medium", "i-drift": "t3.large"})
        inspector = Ec2Inspector(client=client)
        expectations = [
            InstanceExpectation("aws_instance.sync", "i-sync", "t3.medium"),
            InstanceExpectation("aws_instance.drift", "i-drift", "t3.medium"),
            InstanceExpectation("aws_instance.missing", "i-missing", "t3.small"),
        ]

        results = inspector.inspect(expectations)

        self.assertEqual([result.status for result in results], ["IN_SYNC", "DRIFTED", "MISSING"])
        self.assertEqual([result.actual for result in results], ["t3.medium", "t3.large", None])
        self.assertEqual(client.requested_ids, ["i-sync", "i-drift", "i-missing"])

    def test_deduplicates_instance_ids_for_aws_request(self) -> None:
        client = FakeEc2Client({"i-same": "t3.medium"})
        inspector = Ec2Inspector(client=client)
        expectations = [
            InstanceExpectation("aws_instance.first", "i-same", "t3.medium"),
            InstanceExpectation("aws_instance.second", "i-same", "t3.medium"),
        ]

        inspector.inspect(expectations)

        self.assertEqual(client.requested_ids, ["i-same"])

    def test_empty_expectations_make_no_aws_request(self) -> None:
        client = FakeEc2Client({})

        self.assertEqual(Ec2Inspector(client=client).inspect([]), [])
        self.assertEqual(client.requested_ids, [])


if __name__ == "__main__":
    unittest.main()
