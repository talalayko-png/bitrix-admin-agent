from src.connectors.bitrix24.webhook import (
    normalize_event,
    parse_bracketed,
    verify_application_token,
)


def test_parse_bracketed_nested():
    items = [
        ("event", "ONCRMDYNAMICITEMUPDATE"),
        ("data[FIELDS][ID]", "42"),
        ("data[FIELDS][ENTITY_TYPE_ID]", "1030"),
        ("auth[application_token]", "tok"),
    ]
    parsed = parse_bracketed(items)
    assert parsed["data"]["FIELDS"]["ID"] == "42"
    assert parsed["data"]["FIELDS"]["ENTITY_TYPE_ID"] == "1030"
    assert parsed["auth"]["application_token"] == "tok"


def test_normalize_event_smartprocess():
    parsed = {
        "event": "ONCRMDYNAMICITEMUPDATE",
        "data": {"FIELDS": {"ID": "42", "ENTITY_TYPE_ID": "1030", "STAGE_ID": "S1"}},
        "auth": {"application_token": "tok"},
    }
    n = normalize_event(parsed)
    assert n["event"] == "ONCRMDYNAMICITEMUPDATE"
    assert n["payload"]["entity_type_id"] == "1030"
    assert n["payload"]["item_id"] == "42"
    assert n["payload"]["stage_id"] == "S1"
    assert n["application_token"] == "tok"


def test_normalize_event_keeps_legacy_keys():
    # legacy JSON shape used by deal/contact/payment workflows still survives
    n = normalize_event({"event": "deal.update", "data": {"deal_id": "1001", "stage": "WON"}})
    assert n["payload"]["deal_id"] == "1001"
    assert n["payload"]["stage"] == "WON"


def test_verify_application_token():
    assert verify_application_token("s3cr3t", "s3cr3t") is True
    assert verify_application_token("s3cr3t", "other") is False
    assert verify_application_token("", "x") is False
    assert verify_application_token("s", None) is False


def test_form_webhook_valid_token_triggers_supplier_docs(client, monkeypatch):
    monkeypatch.setenv("BITRIX24_INBOUND_WEBHOOK_SECRET", "tok")
    monkeypatch.setenv("SUPPLIER_DOCS_ENTITY_TYPE_ID", "1030")
    from src.config import reload_settings

    reload_settings()

    data = {
        "event": "ONCRMDYNAMICITEMUPDATE",
        "data[FIELDS][ID]": "42",
        "data[FIELDS][ENTITY_TYPE_ID]": "1030",
        "data[FIELDS][STAGE_ID]": "S1",
        "auth[application_token]": "tok",
    }
    resp = client.post("/webhooks/bitrix24", data=data)
    assert resp.status_code == 200
    assert len(resp.json()["operation_ids"]) == 1


def test_form_webhook_bad_token_rejected(client, monkeypatch):
    monkeypatch.setenv("BITRIX24_INBOUND_WEBHOOK_SECRET", "tok")
    from src.config import reload_settings

    reload_settings()

    data = {
        "event": "ONCRMDYNAMICITEMUPDATE",
        "data[FIELDS][ID]": "42",
        "auth[application_token]": "WRONG",
    }
    assert client.post("/webhooks/bitrix24", data=data).status_code == 401
