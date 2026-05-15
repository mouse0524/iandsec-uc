import unittest

from app.core.middlewares import HttpAuditLogMiddleware
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


if __name__ == "__main__":
    unittest.main()
