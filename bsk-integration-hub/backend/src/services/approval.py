"""Approval gate and dangerous-action policy helpers."""

from __future__ import annotations

from src.config import Settings

# Irreversible / destructive operation types that the dangerous-actions policy
# blocks when ``dangerous_actions_disabled`` is on.
DANGEROUS_TYPES = {"order_delete", "invoice_void"}


def needs_approval(settings: Settings, op_type: str, draft_flag: bool = False) -> bool:
    """An operation needs manual approval if the workflow flagged it, the global
    ``approval_required`` switch is on, or its type is in ``APPROVAL_REQUIRED_FOR``."""
    return (
        bool(draft_flag)
        or settings.approval_required
        or op_type in settings.approval_required_set
    )


def is_dangerous(op_type: str) -> bool:
    return op_type in DANGEROUS_TYPES


def dangerous_blocked(settings: Settings, op_type: str) -> bool:
    """True when the type is dangerous and the policy disables dangerous actions."""
    return settings.dangerous_actions_disabled and is_dangerous(op_type)
