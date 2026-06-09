"""Entity mapping service: links between Bitrix24 and MoySklad entities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import EntityLink


class MappingService:
    @staticmethod
    def upsert(
        session: Session,
        b24_type: str,
        b24_id: str,
        ms_type: str,
        ms_id: str,
        meta: dict[str, Any] | None = None,
    ) -> EntityLink:
        stmt = select(EntityLink).where(
            EntityLink.b24_type == b24_type,
            EntityLink.b24_id == b24_id,
            EntityLink.ms_type == ms_type,
            EntityLink.ms_id == ms_id,
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            if meta is not None:
                existing.meta = meta
            return existing
        link = EntityLink(
            b24_type=b24_type,
            b24_id=b24_id,
            ms_type=ms_type,
            ms_id=ms_id,
            meta=meta,
        )
        session.add(link)
        return link

    @staticmethod
    def list(session: Session, limit: int = 100, offset: int = 0) -> list[EntityLink]:
        stmt = (
            select(EntityLink)
            .order_by(EntityLink.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def delete(session: Session, link_id: int) -> bool:
        link = session.get(EntityLink, link_id)
        if link is None:
            return False
        session.delete(link)
        return True
