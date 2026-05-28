from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.webdav import webdav as webdav_module


def _client():
    app = FastAPI()
    app.include_router(webdav_module.public_router, prefix="/api/v1/public/webdav")
    return TestClient(app)


def test_public_direct_download_redirects_to_webdav_credential_url(monkeypatch):
    controller = SimpleNamespace(
        verify_direct_download_signature=AsyncMock(return_value=None),
        get_direct_download_url=AsyncMock(return_value="http://user:pass@dav.example.com/webdav/demo.txt"),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)

    response = _client().get(
        "/api/v1/public/webdav/download",
        params={"path": "/demo.txt", "ts": 100, "sig": "abc"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://user:pass@dav.example.com/webdav/demo.txt"
    controller.verify_direct_download_signature.assert_awaited_once_with(path="/demo.txt", ts=100, sig="abc")
    controller.get_direct_download_url.assert_awaited_once_with("/demo.txt")


def test_public_direct_download_rejects_unsigned_request(monkeypatch):
    controller = SimpleNamespace(
        verify_direct_download_signature=AsyncMock(side_effect=AssertionError("signature should be checked after params")),
        get_direct_download_url=AsyncMock(side_effect=AssertionError("unsigned download must not be redirected")),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)

    response = _client().get(
        "/api/v1/public/webdav/download",
        params={"path": "/demo.txt"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json()["code"] == 400
    controller.verify_direct_download_signature.assert_not_called()
    controller.get_direct_download_url.assert_not_called()


def test_public_share_download_redirects_to_webdav_credential_url(monkeypatch):
    share = SimpleNamespace(file_path="/shared/demo.txt", file_name="demo.txt")
    controller = SimpleNamespace(
        verify_share_signature=AsyncMock(return_value=None),
        get_share=AsyncMock(return_value=share),
        get_direct_download_url=AsyncMock(return_value="http://user:pass@dav.example.com/webdav/shared/demo.txt"),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)
    monkeypatch.setattr(webdav_module, "execute_redis", AsyncMock(return_value=None))

    response = _client().get(
        "/api/v1/public/webdav/share/download",
        params={"code": "share-code", "ts": 100, "sig": "abc"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://user:pass@dav.example.com/webdav/shared/demo.txt"
    controller.verify_share_signature.assert_awaited_once_with(code="share-code", ts=100, sig="abc")
    controller.get_share.assert_awaited_once_with("share-code")
    controller.get_direct_download_url.assert_awaited_once_with("/shared/demo.txt")


def test_public_share_download_rejects_unsigned_request(monkeypatch):
    controller = SimpleNamespace(
        verify_share_signature=AsyncMock(side_effect=AssertionError("signature should be checked after params")),
        get_share=AsyncMock(side_effect=AssertionError("unsigned share must not be loaded")),
        get_direct_download_url=AsyncMock(side_effect=AssertionError("unsigned share must not be redirected")),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)

    response = _client().get(
        "/api/v1/public/webdav/share/download",
        params={"code": "share-code"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json()["code"] == 400
    controller.verify_share_signature.assert_not_called()
    controller.get_share.assert_not_called()
    controller.get_direct_download_url.assert_not_called()
