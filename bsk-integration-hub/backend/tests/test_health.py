def test_public_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dry_run"] is True
    assert body["real_api_enabled"] is False


def test_root_info(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "bsk-integration-hub"


def test_admin_health_requires_token(client):
    assert client.get("/api/admin/health").status_code == 401


def test_admin_health_with_token(client, auth):
    resp = client.get("/api/admin/health", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_admin_health_wrong_token(client):
    resp = client.get("/api/admin/health", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
