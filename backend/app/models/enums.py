from __future__ import annotations

import enum


class ReviewStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class FeedbackVerdict(str, enum.Enum):
    TRUE_POSITIVE = "tp"
    FALSE_POSITIVE = "fp"
    FALSE_NEGATIVE = "fn"
    SKIPPED = "skip"


class AuditEventType(str, enum.Enum):
    RUN_CREATED = "run_created"
    WORKER_STARTED = "worker_started"
    WORKER_COMPLETED = "worker_completed"
    DETECTOR_FINISHED = "detector_finished"
    RUN_FAILED = "run_failed"


class IODirection(str, enum.Enum):
    IN = "in"
    OUT = "out"


class WalletTransactionType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class AIFindingStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
