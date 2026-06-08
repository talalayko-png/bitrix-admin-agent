"""Approval gate helpers."""

from __future__ import annotations

from src.config import Settings


def needs_approval(settings: Settings, op_type: str, draft_flag: bool = False) -> bool:
    """An operation needs manual approval if the workflow flagged it or its type
    is listed in ``APPROVAL_REQUIRED_FOR``."""
    return bool(draft_flag) or op_type in settings.approval_required_set
