from types import SimpleNamespace

import pytest
from fastapi.responses import RedirectResponse, StreamingResponse

from app.api.v1.webdav import webdav as webdav_api


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRequest:
    def __init__(self, user_agent: str):
        self.headers = {"user-agent": user_agent}
        self.client = SimpleNamespace(host="127.0.0.1")


class FakeUserQuery:
    async def first(self):
        return SimpleNamespace(id=7, alias="分享人", username="creator")


def fake_user_filter(**kwargs):
    return FakeUserQuery()


@pytest.mark.anyio
async def test_share_download_redirects_non_apple_devices(monkeypatch):
    calls = []

    async def fake_execute_redis(*args, **kwargs):
        if args and args[0] == "get":
            return None
        return 1

    async def fake_verify_share_signature(*, code, ts, sig):
        return None

    async def fake_get_share(code):
        return SimpleNamespace(file_path="/files/demo.zip", created_by=7)

    async def fake_get_direct_download_url(file_path):
        return "https://user:pass@webdav.example.com/files/demo.zip"

    async def fake_record_download_log(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(webdav_api, "execute_redis", fake_execute_redis)
    monkeypatch.setattr(webdav_api.webdav_controller, "verify_share_signature", fake_verify_share_signature)
    monkeypatch.setattr(webdav_api.webdav_controller, "get_share", fake_get_share)
    monkeypatch.setattr(webdav_api.webdav_controller, "get_direct_download_url", fake_get_direct_download_url)
    monkeypatch.setattr(webdav_api.webdav_controller, "record_download_log", fake_record_download_log)
    monkeypatch.setattr(webdav_api.User, "filter", fake_user_filter)

    response = await webdav_api.webdav_share_download(
        FakeRequest("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"),
        code="abc123",
        ts=1782701857,
        sig="sig",
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == "https://user:pass@webdav.example.com/files/demo.zip"
    assert calls == [
        {
            "download_type": "share",
            "file_path": "/files/demo.zip",
            "share_code": "abc123",
            "downloader_id": 7,
            "downloader_name": "分享人",
            "source_ip": "127.0.0.1",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
            "referer": "",
        }
    ]


@pytest.mark.anyio
async def test_share_download_rate_limits_valid_links(monkeypatch):
    async def fake_execute_redis(*args, **kwargs):
        if args and args[0] == "get":
            return None
        if args and args[0] == "incr" and str(args[1]).startswith("webdav:share:hit:"):
            return 31
        return 1

    async def fake_verify_share_signature(*, code, ts, sig):
        return None

    monkeypatch.setattr(webdav_api, "execute_redis", fake_execute_redis)
    monkeypatch.setattr(webdav_api.webdav_controller, "verify_share_signature", fake_verify_share_signature)

    response = await webdav_api.webdav_share_download(
        FakeRequest("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"),
        code="abc123",
        ts=1782701857,
        sig="sig",
    )

    assert response.status_code == 429


@pytest.mark.anyio
async def test_share_download_streams_for_apple_devices(monkeypatch):
    async def fake_execute_redis(*args, **kwargs):
        if args and args[0] == "get":
            return None
        return 1

    async def fake_verify_share_signature(*, code, ts, sig):
        return None

    async def fake_get_share(code):
        return SimpleNamespace(file_path="/files/demo.zip", created_by=7)

    async def fake_download_stream(file_path):
        async def iterator():
            yield b"demo"

        return iterator, {"content-type": "application/zip"}

    monkeypatch.setattr(webdav_api, "execute_redis", fake_execute_redis)
    monkeypatch.setattr(webdav_api.webdav_controller, "verify_share_signature", fake_verify_share_signature)
    monkeypatch.setattr(webdav_api.webdav_controller, "get_share", fake_get_share)
    monkeypatch.setattr(webdav_api.webdav_controller, "download_stream", fake_download_stream)
    monkeypatch.setattr(webdav_api.User, "filter", fake_user_filter)

    response = await webdav_api.webdav_share_download(
        FakeRequest("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"),
        code="abc123",
        ts=1782701857,
        sig="sig",
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/zip"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''demo.zip"
    assert "location" not in response.headers


@pytest.mark.anyio
async def test_share_download_replaces_non_latin_upstream_download_filename(monkeypatch):
    async def fake_execute_redis(*args, **kwargs):
        if args and args[0] == "get":
            return None
        return 1

    async def fake_verify_share_signature(*, code, ts, sig):
        return None

    async def fake_get_share(code):
        return SimpleNamespace(file_path="/files/Windows安装包必须认证通过.rtf", created_by=7)

    async def fake_download_stream(file_path):
        async def iterator():
            yield b"demo"

        return iterator, {
            "content-type": "application/rtf",
            "content-disposition": 'attachment; filename="Windows安装包必须认证通过.rtf"',
        }

    monkeypatch.setattr(webdav_api, "execute_redis", fake_execute_redis)
    monkeypatch.setattr(webdav_api.webdav_controller, "verify_share_signature", fake_verify_share_signature)
    monkeypatch.setattr(webdav_api.webdav_controller, "get_share", fake_get_share)
    monkeypatch.setattr(webdav_api.webdav_controller, "download_stream", fake_download_stream)
    monkeypatch.setattr(webdav_api.User, "filter", fake_user_filter)

    response = await webdav_api.webdav_share_download(
        FakeRequest("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15"),
        code="abc123",
        ts=1782702696,
        sig="sig",
    )

    assert isinstance(response, StreamingResponse)
    assert response.headers["content-disposition"].startswith("attachment; filename*=UTF-8''Windows")
    response.headers["content-disposition"].encode("latin-1")
