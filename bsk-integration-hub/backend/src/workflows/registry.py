"""Workflow registry."""

from __future__ import annotations

from src.workflows.base import Workflow
from src.workflows.contact_to_counterparty import ContactToCounterpartyWorkflow
from src.workflows.create_supplier_docs import CreateSupplierDocsWorkflow
from src.workflows.deal_to_order import DealToOrderWorkflow
from src.workflows.payment_sync import PaymentSyncWorkflow
from src.workflows.product_sync import ProductSyncWorkflow

_WORKFLOWS: list[Workflow] = [
    DealToOrderWorkflow(),
    ContactToCounterpartyWorkflow(),
    ProductSyncWorkflow(),
    PaymentSyncWorkflow(),
    CreateSupplierDocsWorkflow(),
]


def all_workflows() -> list[Workflow]:
    return list(_WORKFLOWS)


def get_workflow(key_or_type: str | None) -> Workflow | None:
    if not key_or_type:
        return None
    for wf in _WORKFLOWS:
        if wf.key == key_or_type or wf.type == key_or_type:
            return wf
    return None
