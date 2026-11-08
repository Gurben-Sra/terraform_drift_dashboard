import json
import tempfile
import unittest
from pathlib import Path

from terraform_drift_dashboard.state import StateFileError, load_instance_expectations


class StateReaderTests(unittest.TestCase):
    def write_state(self, directory: str, state: object) -> Path:
        path = Path(directory) / "terraform.tfstate"
        path.write_text(json.dumps(state), encoding="utf-8")
        return path

    def test_loads_managed_instances_and_ignores_data_sources_and_other_types(self) -> None:
        state = {
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "app",
                    "instances": [
                        {
                            "index_key": 0,
                            "attributes": {"id": "i-123", "instance_type": "t3.medium"},
                        }
                    ],
                },
                {
                    "mode": "data",
                    "type": "aws_instance",
                    "name": "lookup",
                    "instances": [],
                },
                {
                    "mode": "managed",
                    "type": "aws_security_group",
                    "name": "app",
                    "instances": [],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_state(directory, state)

            result = load_instance_expectations(path)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].address, "aws_instance.app[0]")
        self.assertEqual(result[0].instance_id, "i-123")
        self.assertEqual(result[0].expected_instance_type, "t3.medium")

    def test_includes_module_and_string_instance_key_in_address(self) -> None:
        state = {
            "resources": [
                {
                    "module": "module.production",
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "app",
                    "instances": [
                        {
                            "index_key": "blue",
                            "attributes": {"id": "i-123", "instance_type": "t3.medium"},
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            result = load_instance_expectations(self.write_state(directory, state))

        self.assertEqual(result[0].address, 'module.production.aws_instance.app["blue"]')

    def test_rejects_malformed_state_and_missing_instance_type(self) -> None:
        invalid_states = [
            {},
            {"resources": [{"mode": "managed", "type": "aws_instance", "name": "app"}]},
            {
                "resources": [
                    {
                        "mode": "managed",
                        "type": "aws_instance",
                        "name": "app",
                        "instances": [{"attributes": {"id": "i-123"}}],
                    }
                ]
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            for state in invalid_states:
                with self.subTest(state=state):
                    with self.assertRaises(StateFileError):
                        load_instance_expectations(self.write_state(directory, state))


if __name__ == "__main__":
    unittest.main()
