import unittest
from unittest.mock import patch

from app.core.middlewares import HttpAuditLogMiddleware
from app.services.security import _is_private_hostname
from app.services.skill_know.openai_client import SkillKnowOpenAIClient


class SecurityControlsTestCase(unittest.TestCase):
    def test_audit_log_masks_sensitive_fields(self):
        middleware = HttpAuditLogMiddleware(app=None, methods=["POST"], exclude_paths=[])
        payload = {
            "username": "demo",
            "password": "secret",
            "nested": {"smtp_password": "mail-secret", "safe": "value"},
            "items": [{"token": "jwt", "name": "x"}],
        }

        masked = middleware._mask_sensitive(payload)

        self.assertEqual(masked["password"], "******")
        self.assertEqual(masked["nested"]["smtp_password"], "******")
        self.assertEqual(masked["nested"]["safe"], "value")
        self.assertEqual(masked["items"][0]["token"], "******")

    def test_openai_compatible_url_allows_public_http(self):
        self.assertEqual(
            SkillKnowOpenAIClient._validate_openai_compatible_url("http://api.openai.com/v1", label="LLM"),
            "http://api.openai.com/v1",
        )

    def test_openai_compatible_url_rejects_private_http(self):
        with self.assertRaises(RuntimeError):
            SkillKnowOpenAIClient._validate_openai_compatible_url("http://192.168.2.127:11434/v1", label="LLM")

    def test_ollama_url_allows_http(self):
        self.assertEqual(
            SkillKnowOpenAIClient._validate_ollama_url("http://192.168.2.127:11434", label="Ollama"),
            "http://192.168.2.127:11434",
        )

    def test_model_base_url_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "认证信息"):
            SkillKnowOpenAIClient._validate_openai_compatible_url("http://user:pass@example.com/v1", label="LLM")

    def test_chat_models_accepts_up_to_five_fallback_models(self):
        models = SkillKnowOpenAIClient._chat_models(
            {"llm_chat_model": "qwen-plus, qwen-max\nqwen-turbo；gpt-4o;gpt-4o-mini"},
            default="gpt-4o-mini",
        )

        self.assertEqual(models, ["qwen-plus", "qwen-max", "qwen-turbo", "gpt-4o", "gpt-4o-mini"])

    def test_chat_models_limits_fallback_models_to_five(self):
        models = SkillKnowOpenAIClient._chat_models(
            {"llm_chat_model": "m1,m2,m3,m4,m5,m6"},
            default="gpt-4o-mini",
        )

        self.assertEqual(models, ["m1", "m2", "m3", "m4", "m5"])

    def test_message_content_handles_null_choices(self):
        self.assertEqual(SkillKnowOpenAIClient._message_content({"choices": None}), "")

    def test_message_content_handles_top_level_message_object(self):
        self.assertEqual(SkillKnowOpenAIClient._message_content({"message": {"content": "OK"}}), "OK")

    def test_private_hostname_checks_all_resolved_addresses(self):
        resolved = [
            (None, None, None, None, ("8.8.8.8", 0)),
            (None, None, None, None, ("127.0.0.1", 0)),
        ]
        with patch("app.services.security.socket.getaddrinfo", return_value=resolved):
            self.assertTrue(_is_private_hostname("example.com"))


if __name__ == "__main__":
    unittest.main()
