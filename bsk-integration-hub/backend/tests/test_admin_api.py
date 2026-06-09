def _simulate(client, auth, deal_id):
    return client.post(
        "/api/admin/simulate/deal", headers=auth, json={"deal_id": deal_id}
    ).json()["operation_ids"][0]


def test_requires_auth(client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/admin/operations").status_code == 401


def test_dashboard(client, auth):
    resp = client.get("/api/admin/dashboard", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert "counts" in body
    assert body["flags"]["dry_run"] is True
    assert body["flags"]["real_api_enabled"] is False


def test_simulate_and_detail(client, auth):
    op_id = _simulate(client, auth, "2001")
    detail = client.get(f"/api/admin/operations/{op_id}", headers=auth).json()
    assert detail["operation"]["type"] == "deal_to_order"
    assert detail["operation"]["status"] == "succeeded"

    logs = client.get(f"/api/admin/operations/{op_id}/logs", headers=auth).json()
    snaps = client.get(f"/api/admin/operations/{op_id}/snapshots", headers=auth).json()
    assert len(logs) >= 1
    assert len(snaps) == 1


def test_dry_run_preview(client, auth):
    op_id = _simulate(client, auth, "2002")
    plan = client.post(
        f"/api/admin/operations/{op_id}/dry-run", headers=auth
    ).json()
    assert plan["action"] in ("create", "update")
    assert "after" in plan and plan["after"]["externalCode"] == "2002"


def test_workflow_toggle_disables_processing(client, auth):
    upd = client.put(
        "/api/admin/workflows/deal_to_order", headers=auth, json={"enabled": False}
    )
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False

    res = client.post(
        "/api/admin/simulate/deal", headers=auth, json={"deal_id": "3003"}
    ).json()
    assert res["operation_ids"] == []


def test_workflow_list(client, auth):
    rows = client.get("/api/admin/workflows", headers=auth).json()
    keys = {r["key"] for r in rows}
    assert "deal_to_order" in keys


def test_mappings_crud(client, auth):
    created = client.post(
        "/api/admin/mappings",
        headers=auth,
        json={
            "b24_type": "deal",
            "b24_id": "1",
            "ms_type": "customerorder",
            "ms_id": "abc",
        },
    )
    assert created.status_code == 201
    mid = created.json()["id"]

    listing = client.get("/api/admin/mappings", headers=auth).json()
    assert any(m["id"] == mid for m in listing)

    assert client.delete(f"/api/admin/mappings/{mid}", headers=auth).status_code == 204
    assert client.delete(f"/api/admin/mappings/{mid}", headers=auth).status_code == 404


def test_assistant_placeholder(client, auth):
    resp = client.post(
        "/api/admin/assistant/query", headers=auth, json={"question": "why failed?"}
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_approve_and_retry_conflict_on_succeeded(client, auth):
    op_id = _simulate(client, auth, "4004")  # ends succeeded
    assert (
        client.post(
            f"/api/admin/operations/{op_id}/approve", headers=auth, json={}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/admin/operations/{op_id}/retry", headers=auth
        ).status_code
        == 409
    )


def test_settings_view_has_no_secrets(client, auth):
    body = client.get("/api/admin/settings", headers=auth).json()
    assert "admin_api_token" not in body
    assert "moysklad_token" not in body
    assert body["queue_backend"] == "sync"
