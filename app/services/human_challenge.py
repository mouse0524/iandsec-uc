import httpx

from app.controllers.captcha import captcha_controller
from app.controllers.system_setting import system_setting_controller
from app.log import logger
from app.settings import settings


class HumanChallengeService:
    TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def _challenge_type(self, config: dict) -> str:
        challenge_type = str(config.get("login_challenge_type") or "captcha").strip().lower()
        if challenge_type not in {"captcha", "turnstile", "both"}:
            return "captcha"
        return challenge_type

    def requires_captcha(self, config: dict | None = None) -> bool:
        if config is not None and not config.get("login_challenge_enabled", True):
            return False
        return self._challenge_type(config or {}) in {"captcha", "both"}

    def requires_turnstile(self, config: dict | None = None) -> bool:
        if config is not None and not config.get("login_challenge_enabled", True):
            return False
        return self._challenge_type(config or {}) in {"turnstile", "both"}

    async def verify(
        self,
        *,
        captcha_id: str | None = None,
        captcha_code: str | None = None,
        turnstile_token: str | None = None,
        client_ip: str | None = None,
        consume_captcha: bool = True,
        config: dict | None = None,
        log_context: str = "human_challenge",
    ) -> tuple[bool, str]:
        config = config or await system_setting_controller.get_full_dict()
        if not config.get("login_challenge_enabled", True):
            return True, ""
        challenge_type = self._challenge_type(config)

        captcha_valid = False
        if self.requires_captcha(config):
            valid = await captcha_controller.verify_captcha(
                captcha_id or "",
                captcha_code or "",
                consume=consume_captcha,
            )
            if not valid:
                logger.warning("[{}] captcha_invalid captcha_id={}", log_context, captcha_id)
                return False, f"图形验证码错误或已失效，请重试（最多{settings.CAPTCHA_MAX_RETRY}次）"
            captcha_valid = True

        if self.requires_turnstile(config):
            token = (turnstile_token or "").strip()
            secret = (config.get("turnstile_secret_key") or "").strip()
            if not token and challenge_type == "turnstile":
                if not captcha_valid:
                    captcha_valid = await captcha_controller.verify_captcha(
                        captcha_id or "",
                        captcha_code or "",
                        consume=consume_captcha,
                    )
                if captcha_valid:
                    logger.info("[{}] turnstile_fallback_captcha captcha_id={}", log_context, captcha_id)
                    return True, ""
                logger.warning("[{}] turnstile_missing_and_captcha_invalid captcha_id={}", log_context, captcha_id)
                return False, f"请先完成 Cloudflare Turnstile 安全校验或图形验证码（最多{settings.CAPTCHA_MAX_RETRY}次）"
            if not token:
                return False, "请先完成 Cloudflare Turnstile 安全校验"
            if not secret:
                logger.error("[{}] turnstile_secret_missing", log_context)
                return False, "Cloudflare Turnstile Secret Key 未配置"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self.TURNSTILE_VERIFY_URL,
                        data={
                            "secret": secret,
                            "response": token,
                            "remoteip": client_ip or "",
                        },
                    )
                payload = response.json()
            except Exception as exc:
                logger.warning("[{}] turnstile_verify_failed error={}", log_context, repr(exc))
                return False, "Cloudflare Turnstile 校验失败，请稍后重试"
            if response.status_code != 200 or not payload.get("success"):
                logger.warning(
                    "[{}] turnstile_invalid status={} errors={}",
                    log_context,
                    response.status_code,
                    payload.get("error-codes") or [],
                )
                return False, "Cloudflare Turnstile 校验未通过"

        return True, ""


human_challenge_service = HumanChallengeService()
