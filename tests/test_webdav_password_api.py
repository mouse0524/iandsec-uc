from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.webdav import webdav as webdav_module
from app.core.dependency import AuthControl


def _client():
    app = FastAPI()

    async def fake_auth():
        return SimpleNamespace(id=1, username="admin", is_active=True, is_superuser=True)

    app.dependency_overrides[AuthControl.is_authed] = fake_auth
    app.include_router(webdav_module.router, prefix="/api/v1/webdav")
    return TestClient(app)


def test_server_ops_password_endpoint_returns_only_server_ops_password(monkeypatch):
    monkeypatch.setattr(webdav_module, "generate_server_ops_password", lambda: "server-secret")

    response = _client().get("/api/v1/webdav/ops-password")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "password": "server-secret",
        "description": "密码每天变更",
    }


def test_replace_decrypt_password_endpoint_returns_only_replace_decrypt_password(monkeypatch):
    monkeypatch.setattr(webdav_module, "generate_replace_decrypt_password", lambda: "replace-secret")

    response = _client().get("/api/v1/webdav/replace-decrypt-password")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "password": "replace-secret",
        "description": "密码每月变更",
    }
