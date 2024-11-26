"""Base types shared across multiple models."""

from enum import Enum


class SnapshotState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"
