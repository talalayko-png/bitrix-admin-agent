"""Workflow base class.

A workflow:
  * ``matches`` decides whether an inbound event is relevant;
  * ``build_draft`` turns the event into an idempotent operation draft;
  * ``plan`` computes a pure (no-write) diff of what *would* change;
  * ``execute`` records a snapshot and either stops (dry-run) or applies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.domain.entities import OperationDraft, WebhookEnvelope

if TYPE_CHECKING:
    from src.services.context import ExecutionContext


@dataclass
class PlanResult:
    action: str  # create | update | delete | noop
    entity_ref: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    summary: str
    # workflow-internal data (e.g. source ids); never sent to the external API
    meta: dict[str, Any] | None = None


class Workflow(ABC):
    key: str = "base"
    type: str = "noop"
    name: str = "Base workflow"
    trigger_source: str = "system"

    @abstractmethod
    def matches(self, envelope: WebhookEnvelope) -> bool: ...

    @abstractmethod
    def build_draft(self, envelope: WebhookEnvelope) -> OperationDraft | None: ...

    @abstractmethod
    def plan(self, ctx: ExecutionContext, payload: dict[str, Any]) -> PlanResult: ...

    def execute(self, ctx: ExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.plan(ctx, payload)
        ctx.snapshot(
            entity_ref=plan.entity_ref,
            action=plan.action,
            before=plan.before,
            after=plan.after,
        )
        if ctx.settings.dry_run:
            ctx.log("info", f"DRY-RUN: would {plan.action} {plan.entity_ref}: {plan.summary}")
            return {
                "dry_run": True,
                "action": plan.action,
                "entity_ref": plan.entity_ref,
                "summary": plan.summary,
                "after": plan.after,
            }
        result = self.apply(ctx, plan)
        ctx.log("info", f"Applied {plan.action} {plan.entity_ref}")
        return {
            "dry_run": False,
            "action": plan.action,
            "entity_ref": plan.entity_ref,
            "result": result,
        }

    def apply(self, ctx: ExecutionContext, plan: PlanResult) -> dict[str, Any]:
        """Perform the real write. Only reached when dry_run is False."""
        raise NotImplementedError(f"{self.key}: real apply path not implemented")
