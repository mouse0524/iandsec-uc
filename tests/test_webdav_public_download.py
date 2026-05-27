from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.webdav import webdav as webdav_module


def _client():
    app = FastAPI()
    app.include_router(webdav_module.public_router, prefix="/api/v1/public/webdav")
    return TestClient(app)


def test_public_direct_download_redirects_to_public_webdav_url(monkeypatch):
    controller = SimpleNamespace(
        verify_direct_download_signature=AsyncMock(return_value=None),
        get_public_download_url=AsyncMock(return_value="https://files.example.com/public/demo.txt"),
        download_stream=AsyncMock(side_effect=AssertionError("download should not be proxied by the API server")),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)

    response = _client().get(
        "/api/v1/public/webdav/download",
        params={"path": "/demo.txt", "ts": 100, "sig": "abc"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://files.example.com/public/demo.txt"
    controller.verify_direct_download_signature.assert_awaited_once_with(path="/demo.txt", ts=100, sig="abc")
    controller.get_public_download_url.assert_awaited_once_with("/demo.txt")
    controller.download_stream.assert_not_called()


def test_public_share_download_redirects_to_public_webdav_url(monkeypatch):
    share = SimpleNamespace(file_path="/shared/demo.txt", file_name="demo.txt")
    controller = SimpleNamespace(
        verify_share_signature=AsyncMock(return_value=None),
        get_share=AsyncMock(return_value=share),
        get_public_download_url=AsyncMock(return_value="https://files.example.com/public/shared/demo.txt"),
        download_stream=AsyncMock(side_effect=AssertionError("download should not be proxied by the API server")),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)
    monkeypatch.setattr(webdav_module, "execute_redis", AsyncMock(return_value=None))

    response = _client().get(
        "/api/v1/public/webdav/share/download",
        params={"code": "share-code", "ts": 100, "sig": "abc"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://files.example.com/public/shared/demo.txt"
    controller.verify_share_signature.assert_awaited_once_with(code="share-code", ts=100, sig="abc")
    controller.get_share.assert_awaited_once_with("share-code")
    controller.get_public_download_url.assert_awaited_once_with("/shared/demo.txt")
    controller.download_stream.assert_not_called()


def test_public_direct_download_reports_missing_public_base_url(monkeypatch):
    controller = SimpleNamespace(
        verify_direct_download_signature=AsyncMock(return_value=None),
        get_public_download_url=AsyncMock(side_effect=HTTPException(status_code=400, detail="WebDAV公开下载地址未配置")),
        download_stream=AsyncMock(side_effect=AssertionError("download should not be proxied by the API server")),
    )
    monkeypatch.setattr(webdav_module, "webdav_controller", controller)

    response = _client().get(
        "/api/v1/public/webdav/download",
        params={"path": "/demo.txt", "ts": 100, "sig": "abc"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "WebDAV公开下载地址未配置"
    controller.verify_direct_download_signature.assert_awaited_once_with(path="/demo.txt", ts=100, sig="abc")
    controller.get_public_download_url.assert_awaited_once_with("/demo.txt")
    controller.download_stream.assert_not_called()
