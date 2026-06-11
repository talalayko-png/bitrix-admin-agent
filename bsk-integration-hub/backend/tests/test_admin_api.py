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


def test_inspect_smart_process(client, auth):
    resp = client.get(
        "/api/admin/inspect/smart-process?entity_type_id=1030&item_id=42",
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["item"]["id"] == "42"
    assert isinstance(body["field_overview"], list)
    assert any(f["code"] == "ufCrm_PO_ID" for f in body["field_overview"])
    assert body["product_rows"]  # mock item 42 has a product row
    # mock item 42 links deal 1001 -> deal fields come back with titles
    assert body["parent_deal_id"] == "1001"
    assert any(
        f["code"] == "UF_CRM_SKLAD_MS" and f["title"] == "Склад МС"
        for f in body["deal_field_overview"]
    )
    # company ids are resolved to names (поставщик это или покупатель — видно глазами)
    assert body["companies"]["item.companyId"]["title"] == "ООО Поставщик-77"
    # enum ids resolve to labels; raw deal field definitions are exposed too
    delivery = next(
        f for f in body["deal_field_overview"] if f["code"] == "UF_CRM_DELIVERY"
    )
    assert delivery["value_label"] == "ТК"
    assert "items" in body["deal_fields"]["UF_CRM_DELIVERY"]


def test_moysklad_reference_lookups(client, auth):
    stores = client.get("/api/admin/moysklad/stores", headers=auth).json()
    assert {"id": "store-1", "name": "Основной склад"} in stores

    by_code = client.get("/api/admin/moysklad/products?code=K-200", headers=auth).json()
    assert by_code and by_code[0]["id"] == "ms-prod-200"

    by_search = client.get(
        "/api/admin/moysklad/products?search=станок", headers=auth
    ).json()
    assert by_search and by_search[0]["name"] == "Станок ЧПУ"

    assert client.get("/api/admin/moysklad/products", headers=auth).status_code == 422

    cps = client.get(
        "/api/admin/moysklad/counterparties?search=поставщик", headers=auth
    ).json()
    assert cps and cps[0]["id"] == "ms-cp-77"


def test_simulate_smart_item_runs_supplier_docs(client, auth):
    resp = client.post(
        "/api/admin/simulate/smart-item",
        headers=auth,
        json={"entity_type_id": "1030", "item_id": "42", "stage_id": "S1"},
    )
    assert resp.status_code == 200
    ops = resp.json().get("operations") or resp.json().get("operation_ids") or []
    assert ops, f"no operations created: {resp.json()}"


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
    # supplier-docs config is visible (field codes are not secrets)
    assert body["supplier_docs"]["field_ready_date"] == "ufCrm19_1771861585"
    assert body["supplier_docs"]["deal_store_field"] == "UF_CRM_1695973329"
