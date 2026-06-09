"""CRUD + resolution for reference-data mappings (Bitrix24 <-> MoySklad)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import ReferenceMapping
from src.utils.time import utcnow

KINDS = {"product", "counterparty", "store", "organization", "pricetype", "vat"}


class ReferenceMappingService:
    @staticmethod
    def resolve(session: Session, kind: str, b24_value: str) -> ReferenceMapping | None:
        stmt = select(ReferenceMapping).where(
            ReferenceMapping.kind == kind,
            ReferenceMapping.b24_value == str(b24_value),
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list(session: Session, kind: str | None = None) -> list[ReferenceMapping]:
        stmt = select(ReferenceMapping).order_by(ReferenceMapping.kind, ReferenceMapping.b24_value)
        if kind:
            stmt = stmt.where(ReferenceMapping.kind == kind)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def upsert(
        session: Session,
        kind: str,
        b24_value: str,
        ms_type: str,
        ms_id: str,
        ms_name: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ReferenceMapping:
        existing = ReferenceMappingService.resolve(session, kind, b24_value)
        if existing:
            existing.ms_type = ms_type
            existing.ms_id = ms_id
            existing.ms_name = ms_name
            existing.meta = meta
            existing.updated_at = utcnow()
            return existing
        row = ReferenceMapping(
            kind=kind,
            b24_value=str(b24_value),
            ms_type=ms_type,
            ms_id=ms_id,
            ms_name=ms_name,
            meta=meta,
        )
        session.add(row)
        return row

    @staticmethod
    def delete(session: Session, mapping_id: int) -> bool:
        row = session.get(ReferenceMapping, mapping_id)
        if row is None:
            return False
        session.delete(row)
        return True
