import unittest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.controllers.webdav import WebDavController


class WebDavControllerTestCase(unittest.TestCase):
    def test_list_dir_url_keeps_root_without_extra_slash(self):
        self.assertEqual(
            WebDavController._build_list_url("https://dav.example.com/webdav", "/"),
            "https://dav.example.com/webdav/",
        )

    def test_list_dir_url_keeps_child_directory_without_forced_trailing_slash(self):
        self.assertEqual(
            WebDavController._build_list_url("https://dav.example.com/webdav", "/6.0.8"),
            "https://dav.example.com/webdav/6.0.8",
        )

    def test_file_url_does_not_append_trailing_slash(self):
        self.assertEqual(
            WebDavController._build_url("https://dav.example.com/webdav", "/6.0.8/demo.txt"),
            "https://dav.example.com/webdav/6.0.8/demo.txt",
        )

    def test_public_download_url_uses_public_base_when_configured(self):
        controller = WebDavController()
        conf = {
            "webdav_base_url": "https://internal.example.com/webdav",
            "webdav_public_base_url": "https://files.example.com/public",
        }

        self.assertEqual(
            controller.build_public_download_url(conf, "/6.0.8/demo file.txt"),
            "https://files.example.com/public/6.0.8/demo%20file.txt",
        )

    def test_public_download_url_requires_public_base_url(self):
        controller = WebDavController()
        conf = {
            "webdav_base_url": "https://dav.example.com/webdav",
            "webdav_public_base_url": "",
        }

        with self.assertRaises(Exception):
            controller.build_public_download_url(conf, "/demo.txt")

    def test_share_dict_marks_expired_active_share_as_inactive(self):
        controller = WebDavController()
        expired = datetime.now(timezone.utc) - timedelta(seconds=1)
        row = MagicMock(is_active=True, expire_time=expired)

        data = controller._share_to_dict(row, creator_name="admin", download_url="/download")

        self.assertFalse(data["is_active"])
        self.assertTrue(data["is_expired"])
        self.assertEqual(data["status"], "expired")

    def test_list_shares_filters_by_file_name(self):
        asyncio.run(self._assert_list_shares_filters_by_file_name())

    def test_download_stream_follows_redirects(self):
        asyncio.run(self._assert_download_stream_follows_redirects())

    def test_verify_share_signature_treats_ttl_as_hours(self):
        asyncio.run(self._assert_verify_share_signature_treats_ttl_as_hours())

    def test_verify_share_signature_rejects_after_configured_hours(self):
        asyncio.run(self._assert_verify_share_signature_rejects_after_configured_hours())

    async def _assert_list_shares_filters_by_file_name(self):
        controller = WebDavController()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.count = AsyncMock(return_value=0)
        q.offset.return_value = q
        q.limit = AsyncMock(return_value=[])

        with patch("app.controllers.webdav.WebDavShareLink.all", return_value=q):
            await controller.list_shares(
                created_by=None,
                page=1,
                page_size=10,
                include_history=True,
                file_name="demo",
            )

        q.filter.assert_called_once_with(file_name__icontains="demo")

    async def _assert_download_stream_follows_redirects(self):
        controller = WebDavController()
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                302,
                headers={"Location": "https://cdn.example.com/demo.txt"},
            )
            if request.url.host == "dav.example.com"
            else httpx.Response(
                200,
                headers={"Content-Type": "text/plain"},
                content=b"real file",
            )
        )
        conf = {
            "webdav_enabled": True,
            "webdav_base_url": "https://dav.example.com/webdav",
            "webdav_username": "user",
            "webdav_password": "pass",
        }

        with patch.object(controller, "_get_config", AsyncMock(return_value=conf)):
            with patch.object(
                controller,
                "_client",
                lambda conf, timeout: httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=True,
                    transport=transport,
                ),
            ):
                iterator, headers = await controller.download_stream("/demo.txt")
                chunks = [chunk async for chunk in iterator()]

        self.assertEqual(b"".join(chunks), b"real file")
        self.assertEqual(headers.get("content-type"), "text/plain")

    async def _assert_verify_share_signature_treats_ttl_as_hours(self):
        controller = WebDavController()
        now = datetime.now(timezone.utc)
        ts = int((now - timedelta(minutes=30)).timestamp())
        sig = controller._sign("secret", "share-code", ts)
        conf = {
            "webdav_enabled": True,
            "webdav_base_url": "https://dav.example.com/webdav",
            "webdav_username": "user",
            "webdav_password": "pass",
            "webdav_signature_secret": "secret",
            "webdav_signature_ttl": 1,
        }

        with patch.object(controller, "_get_config", AsyncMock(return_value=conf)):
            await controller.verify_share_signature(code="share-code", ts=ts, sig=sig)

    async def _assert_verify_share_signature_rejects_after_configured_hours(self):
        controller = WebDavController()
        now = datetime.now(timezone.utc)
        ts = int((now - timedelta(hours=2)).timestamp())
        sig = controller._sign("secret", "share-code", ts)
        conf = {
            "webdav_enabled": True,
            "webdav_base_url": "https://dav.example.com/webdav",
            "webdav_username": "user",
            "webdav_password": "pass",
            "webdav_signature_secret": "secret",
            "webdav_signature_ttl": 1,
        }

        with patch.object(controller, "_get_config", AsyncMock(return_value=conf)):
            with self.assertRaises(Exception):
                await controller.verify_share_signature(code="share-code", ts=ts, sig=sig)


if __name__ == "__main__":
    unittest.main()
