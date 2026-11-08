"""Shared data structures for drift checks."""

from dataclasses import dataclass
from typing import Literal


DriftStatus = Literal["IN_SYNC", "DRIFTED", "MISSING"]


@dataclass(frozen=True)
class InstanceExpectation:
    address: str
    instance_id: str
    expected_instance_type: str


@dataclass(frozen=True)
class DriftResult:
    address: str
    instance_id: str
    expected: str
    actual: str | None
    status: DriftStatus
