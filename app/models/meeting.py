from enum import StrEnum


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalEntity(StrEnum):
    """Levels of the meeting > topic > action approval hierarchy."""

    MEETING = "meeting"
    TOPIC = "topic"
    ACTION = "action"


class AttendeeType(StrEnum):
    LEAD = "lead"
    BOARD = "board"
    CROSS_BOARD = "cross_board"


TERMINAL_STATUSES = frozenset({ApprovalStatus.APPROVED, ApprovalStatus.REJECTED})
