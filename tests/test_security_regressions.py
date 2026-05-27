import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from app.controllers.captcha import captcha_controller
from app.controllers.system_setting import system_setting_controller
from app.core.init_app import _default_basic_api_filter, _default_basic_api_paths
from app.controllers.ticket import TicketController
from app.services.security import validate_external_service_url
from app.services.skill_know.document_service import skill_know_document_service
from app.services.skill_know.openai_client import SkillKnowOpenAIClient


class SecurityRegressionTestCase(unittest.TestCase):
    def test_default_basic_api_filter_does_not_grant_all_get(self):
        api_filter = str(_default_basic_api_filter())

        self.assertNotIn("method", api_filter.lower())
        self.assertIn("/api/v1/base/update_password", _default_basic_api_paths())

    def test_chunk_upload_id_rejects_path_traversal(self):
        with self.assertRaises(Exception):
            skill_know_document_service._safe_chunk_dir("../outside")

    def test_external_service_url_rejects_insecure_and_private_hosts(self):
        with self.assertRaises(Exception):
            validate_external_service_url("http://example.com/v1", label="LLM")
        with self.assertRaises(Exception):
            validate_external_service_url("https://127.0.0.1/v1", label="LLM")

    def test_external_service_url_accepts_https_public_host(self):
        self.assertEqual(validate_external_service_url("https://api.openai.com/v1", label="LLM"), "https://api.openai.com/v1")

    def test_webdav_url_can_skip_allowed_host_list(self):
        self.assertEqual(
            validate_external_service_url(
                "https://dav.example.com/webdav",
                label="WebDAV Base URL",
                enforce_allowed_hosts=False,
            ),
            "https://dav.example.com/webdav",
        )

    def test_webdav_connection_test_validates_public_download_base_url(self):
        async def run():
            with patch.object(
                system_setting_controller,
                "_get_merged_raw",
                AsyncMock(
                    return_value={
                        "webdav_enabled": True,
                        "webdav_base_url": "https://dav.example.com/webdav",
                        "webdav_username": "user",
                        "webdav_password": "pass",
                    }
                ),
            ), patch("app.controllers.system_setting.httpx.AsyncClient") as mock_client:
                with self.assertRaises(Exception):
                    await system_setting_controller.test_webdav_connection(
                        {
                            "webdav_public_base_url": "http://files.example.com/public",
                        }
                    )
                mock_client.assert_not_called()

        asyncio.run(run())

    def test_openai_compatible_model_url_rejects_private_hosts(self):
        with self.assertRaises(RuntimeError):
            SkillKnowOpenAIClient._validate_openai_compatible_url("http://127.0.0.1:11434/v1", label="LLM对话地址")

    def test_ollama_model_url_allows_private_hosts(self):
        self.assertEqual(
            SkillKnowOpenAIClient._validate_ollama_url("http://127.0.0.1:11434", label="Ollama对话地址"),
            "http://127.0.0.1:11434",
        )

    def test_verify_captcha_without_consume_keeps_value_for_submit(self):
        captcha_id = "test-captcha"
        captcha_controller._set_local_cache(captcha_id, "1234")

        async def run():
            first = await captcha_controller.verify_captcha(captcha_id, "1234", consume=False)
            second = await captcha_controller.verify_captcha(captcha_id, "1234", consume=True)
            return first, second

        first, second = asyncio.run(run())
        self.assertTrue(first)
        self.assertTrue(second)

    def test_chunk_manifest_rejects_other_user(self):
        manifest = {
            "upload_id": "a" * 32,
            "user_id": 1,
            "filename": "demo.md",
            "title": "demo.md",
            "folder_id": None,
            "file_size": 10,
            "file_type": "md",
            "total_chunks": 1,
        }

        async def run():
            with patch.object(skill_know_document_service, "_read_chunk_manifest", AsyncMock(return_value=manifest)):
                await skill_know_document_service.chunk_upload_status("a" * 32, 1, user_id=2)

        with self.assertRaises(Exception):
            asyncio.run(run())

    def test_guest_attachment_binding_rejects_other_session(self):
        controller = TicketController()

        async def run():
            with patch("app.controllers.ticket.execute_redis", AsyncMock(return_value={"1", "2"})):
                await controller.validate_guest_attachment_ids(captcha_id="cap-a", attachment_ids=[1, 3])

        with self.assertRaises(Exception):
            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
