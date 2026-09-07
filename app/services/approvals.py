"""Hierarchical approvals across the meeting > topic > action chain.

Approval state is stored as append-only history: the newest row for an entity is its
current state, and older rows form the audit trail.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataverse import actions_list, approval, meeting, meeting_agendas, topic_intake
from app.models.meeting import TERMINAL_STATUSES, ApprovalEntity, ApprovalStatus


class ApprovalError(RuntimeError):
    """Raised when a decision is rejected by the approval rules."""


@dataclass(frozen=True)
class ApprovalRecord:
    status: ApprovalStatus
    approver_upn: str | None
    comments: str | None
    created_on: datetime


def _as_status(value: str | None) -> ApprovalStatus:
    try:
        return ApprovalStatus(value) if value else ApprovalStatus.DRAFT
    except ValueError:
        return ApprovalStatus.DRAFT


def current_status(database: Session, entity_type: ApprovalEntity, entity_id: str) -> ApprovalStatus:
    """Return the latest recorded status, defaulting to draft when never reviewed."""
    row = database.execute(
        select(approval.c.status)
        .where(approval.c.entity_type == entity_type, approval.c.entity_id == entity_id)
        .order_by(approval.c.created_on.desc(), approval.c.id.desc())
        .limit(1)
    ).first()
    return _as_status(row[0] if row else None)


def statuses_for(
    database: Session, entity_type: ApprovalEntity, entity_ids: list[str]
) -> dict[str, ApprovalStatus]:
    """Resolve statuses for many entities without issuing a query per entity."""
    if not entity_ids:
        return {}
    rows = database.execute(
        select(approval.c.entity_id, approval.c.status, approval.c.created_on)
        .where(approval.c.entity_type == entity_type, approval.c.entity_id.in_(entity_ids))
        .order_by(approval.c.created_on.asc(), approval.c.id.asc())
    ).all()

    resolved: dict[str, ApprovalStatus] = {entity_id: ApprovalStatus.DRAFT for entity_id in entity_ids}
    for entity_id, status, _created_on in rows:
        resolved[entity_id] = _as_status(status)
    return resolved


def history(database: Session, entity_type: ApprovalEntity, entity_id: str) -> list[ApprovalRecord]:
    rows = database.execute(
        select(approval.c.status, approval.c.approver_upn, approval.c.comments, approval.c.created_on)
        .where(approval.c.entity_type == entity_type, approval.c.entity_id == entity_id)
        .order_by(approval.c.created_on.desc(), approval.c.id.desc())
    ).all()
    return [
        ApprovalRecord(
            status=_as_status(status),
            approver_upn=approver_upn,
            comments=comments,
            created_on=created_on,
        )
        for status, approver_upn, comments, created_on in rows
    ]


def topic_ids_for_meeting(database: Session, meeting_id: str) -> list[str]:
    return list(
        database.execute(
            select(meeting_agendas.c.topic_id)
            .where(meeting_agendas.c.meeting_id == meeting_id)
            .order_by(meeting_agendas.c.sequence, meeting_agendas.c.created_on)
        ).scalars()
    )


def action_ids_for_topic(database: Session, topic_id: str) -> list[str]:
    return list(
        database.execute(
            select(actions_list.c.id).where(actions_list.c.topic_id == topic_id)
        ).scalars()
    )


def topic_blockers(database: Session, topic_id: str) -> list[str]:
    """Actions that still prevent the topic from being approved."""
    action_ids = action_ids_for_topic(database, topic_id)
    if not action_ids:
        return []
    statuses = statuses_for(database, ApprovalEntity.ACTION, action_ids)
    titles = dict(
        database.execute(
            select(actions_list.c.id, actions_list.c.title).where(actions_list.c.id.in_(action_ids))
        ).all()
    )
    return [
        titles.get(action_id, action_id)
        for action_id, status in statuses.items()
        if status not in TERMINAL_STATUSES
    ]


def meeting_blockers(database: Session, meeting_id: str) -> list[str]:
    """Topics that still prevent the meeting from being approved."""
    topic_ids = topic_ids_for_meeting(database, meeting_id)
    if not topic_ids:
        return []
    statuses = statuses_for(database, ApprovalEntity.TOPIC, topic_ids)
    titles = dict(
        database.execute(
            select(topic_intake.c.id, topic_intake.c.title).where(topic_intake.c.id.in_(topic_ids))
        ).all()
    )
    return [
        titles.get(topic_id, topic_id)
        for topic_id, status in statuses.items()
        if status != ApprovalStatus.APPROVED
    ]


def _entity_exists(database: Session, entity_type: ApprovalEntity, entity_id: str) -> bool:
    table = {
        ApprovalEntity.MEETING: meeting,
        ApprovalEntity.TOPIC: topic_intake,
        ApprovalEntity.ACTION: actions_list,
    }[entity_type]
    return database.execute(select(table.c.id).where(table.c.id == entity_id)).first() is not None


def _guard_hierarchy(database: Session, entity_type: ApprovalEntity, entity_id: str) -> None:
    """Approval only flows upward once every child below has been settled."""
    if entity_type is ApprovalEntity.TOPIC:
        blockers = topic_blockers(database, entity_id)
        if blockers:
            raise ApprovalError(
                "This topic cannot be approved until its actions are resolved: " + ", ".join(blockers)
            )
    elif entity_type is ApprovalEntity.MEETING:
        blockers = meeting_blockers(database, entity_id)
        if blockers:
            raise ApprovalError(
                "This meeting cannot be approved until every topic is approved: " + ", ".join(blockers)
            )


def record_decision(
    database: Session,
    entity_type: ApprovalEntity,
    entity_id: str,
    status: ApprovalStatus,
    approver_upn: str,
    comments: str | None = None,
) -> ApprovalStatus:
    """Record an approval decision after validating the hierarchy rules."""
    if not _entity_exists(database, entity_type, entity_id):
        raise LookupError(f"{entity_type.value.title()} {entity_id} was not found.")

    if status is ApprovalStatus.APPROVED:
        _guard_hierarchy(database, entity_type, entity_id)

    if current_status(database, entity_type, entity_id) == status:
        return status

    database.execute(
        approval.insert().values(
            id=str(uuid4()),
            entity_type=entity_type.value,
            entity_id=entity_id,
            status=status.value,
            approver_upn=approver_upn,
            comments=comments,
            created_on=datetime.now(timezone.utc),
        )
    )
    database.commit()
    return status
