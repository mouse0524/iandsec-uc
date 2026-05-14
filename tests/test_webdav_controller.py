import unittest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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


if __name__ == "__main__":
    unittest.main()
