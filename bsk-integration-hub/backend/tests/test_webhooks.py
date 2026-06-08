import hashlib
import hmac
import json


def test_bitrix_webhook_creates_operation(client, auth):
    payload = {"event": "deal.update", "data": {"deal_id": "1001", "stage": "WON"}}
    resp = client.post("/webhooks/bitrix24", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["operation_ids"]) == 1

    op_id = body["operation_ids"][0]
    detail = client.get(f"/api/admin/operations/{op_id}", headers=auth).json()
    assert detail["operation"]["status"] == "succeeded"
    assert detail["operation"]["result"]["action"] == "create"
    assert len(detail["snapshots"]) == 1


def test_idempotent_webhook(client, auth):
    payload = {"event": "deal.update", "data": {"deal_id": "1001", "stage": "WON"}}
    r1 = client.post("/webhooks/bitrix24", json=payload).json()
    r2 = client.post("/webhooks/bitrix24", json=payload).json()
    assert r1["operation_ids"] == r2["operation_ids"]

    ops = client.get("/api/admin/operations", headers=auth).json()
    deal_ops = [o for o in ops if o["type"] == "deal_to_order"]
    assert len(deal_ops) == 1


def test_unmatched_event_creates_no_operation(client):
    payload = {"event": "ONCRMLEADADD", "data": {"id": "5"}}
    resp = client.post("/webhooks/bitrix24", json=payload)
    assert resp.status_code == 200
    assert resp.json()["operation_ids"] == []


def test_signature_rejected_when_secret_set(client, monkeypatch):
    monkeypatch.setenv("BITRIX24_INBOUND_WEBHOOK_SECRET", "s3cr3t")
    from src.config import reload_settings

    reload_settings()

    payload = {"event": "deal.update", "data": {"deal_id": "1001"}}
    resp = client.post("/webhooks/bitrix24", json=payload)  # no signature
    assert resp.status_code == 401


def test_signature_accepted_when_valid(client, monkeypatch):
    secret = "s3cr3t"
    monkeypatch.setenv("BITRIX24_INBOUND_WEBHOOK_SECRET", secret)
    from src.config import reload_settings

    reload_settings()

    payload = {"event": "deal.update", "data": {"deal_id": "1001", "stage": "WON"}}
    raw = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    resp = client.post(
        "/webhooks/bitrix24",
        content=raw,
        headers={"content-type": "application/json", "x-signature": sig},
    )
    assert resp.status_code == 200
    assert len(resp.json()["operation_ids"]) == 1


def test_moysklad_webhook_accepts_event(client):
    body = {"events": [{"action": "UPDATE", "meta": {}}]}
    resp = client.post("/webhooks/moysklad", json=body)
    assert resp.status_code == 200
    # no MoySklad workflow yet -> stored but no operations
    assert resp.json()["operation_ids"] == []
