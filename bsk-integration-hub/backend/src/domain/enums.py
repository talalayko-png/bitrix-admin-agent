"""Domain enumerations."""

from __future__ import annotations

import enum


class Source(enum.StrEnum):
    bitrix24 = "bitrix24"
    moysklad = "moysklad"
    admin = "admin"
    system = "system"


class OperationStatus(enum.StrEnum):
    pending = "pending"
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    dead = "dead"

    @property
    def is_terminal(self) -> bool:
        return self in {
            OperationStatus.succeeded,
            OperationStatus.cancelled,
            OperationStatus.dead,
        }


# Known operation types. Workflows may introduce their own string types too.
class OperationType(enum.StrEnum):
    deal_to_order = "deal_to_order"
    order_to_deal = "order_to_deal"
    order_delete = "order_delete"
    invoice_void = "invoice_void"
    noop = "noop"


class ExecuteResult(enum.StrEnum):
    succeeded = "succeeded"
    failed = "failed"
    retry = "retry"
    skipped = "skipped"
    awaiting_approval = "awaiting_approval"
    locked = "locked"
