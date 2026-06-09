"""Seed default rows (workflow configs) so they appear in the admin panel."""

from __future__ import annotations

from sqlalchemy import select

from src.db.base import session_scope
from src.db.models import WorkflowConfig
from src.workflows.registry import all_workflows


def seed_workflows() -> None:
    with session_scope() as session:
        existing = {
            c.key for c in session.execute(select(WorkflowConfig)).scalars().all()
        }
        for wf in all_workflows():
            if wf.key not in existing:
                session.add(
                    WorkflowConfig(
                        key=wf.key,
                        name=wf.name,
                        trigger_source=wf.trigger_source,
                        enabled=True,
                        config={},
                    )
                )
