"""Small query helpers used by services and the admin API."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Operation, OperationLog, Snapshot
from src.domain.enums import OperationStatus


def get_operation(session: Session, operation_id: int) -> Operation | None:
    return session.get(Operation, operation_id)


def find_operation_by_key(session: Session, idempotency_key: str) -> Operation | None:
    stmt = select(Operation).where(Operation.idempotency_key == idempotency_key)
    return session.execute(stmt).scalar_one_or_none()


def list_operations(
    session: Session,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Operation]:
    stmt = select(Operation).order_by(Operation.created_at.desc())
    if status:
        stmt = stmt.where(Operation.status == status)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.execute(stmt).scalars().all())


def count_by_status(session: Session) -> dict[str, int]:
    stmt = select(Operation.status, func.count()).group_by(Operation.status)
    counts = {status.value: 0 for status in OperationStatus}
    for status, count in session.execute(stmt).all():
        counts[status] = count
    return counts


def operation_logs(session: Session, operation_id: int) -> list[OperationLog]:
    stmt = (
        select(OperationLog)
        .where(OperationLog.operation_id == operation_id)
        .order_by(OperationLog.created_at.asc(), OperationLog.id.asc())
    )
    return list(session.execute(stmt).scalars().all())


def operation_snapshots(session: Session, operation_id: int) -> list[Snapshot]:
    stmt = (
        select(Snapshot)
        .where(Snapshot.operation_id == operation_id)
        .order_by(Snapshot.created_at.asc(), Snapshot.id.asc())
    )
    return list(session.execute(stmt).scalars().all())
