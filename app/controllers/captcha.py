import base64
import io
import random
import string
import unicodedata
import uuid

from PIL import Image, ImageDraw, ImageFont

from app.core.redis_client import execute_redis
from app.log import logger
from app.settings import settings


class CaptchaController:
    @staticmethod
    def _load_font(font_size: int):
        font_candidates = [
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arial.ttf",
        ]
        for font_name in font_candidates:
            try:
                return ImageFont.truetype(font_name, font_size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _generate_code(length: int = 4) -> str:
        chars = "23456789"
        return "".join(random.choice(chars) for _ in range(length))

    @staticmethod
    def _normalize_code(code: str) -> str:
        if code is None:
            return ""
        normalized = unicodedata.normalize("NFKC", code)
        return normalized.strip().replace(" ", "").lower()

    @staticmethod
    def _generate_image_base64(code: str) -> str:
        width, height = 120, 34
        image = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = CaptchaController._load_font(24)

        for i, ch in enumerate(code):
            bbox = draw.textbbox((0, 0), ch, font=font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]
            x = 12 + i * 26 + (18 - char_width) / 2 - bbox[0]
            y = (height - char_height) / 2 - bbox[1]
            draw.text((x, y), ch, fill=(16, 16, 16), font=font)

        for _ in range(4):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line((x1, y1, x2, y2), fill=(168, 168, 168), width=1)

        for _ in range(18):
            draw.point((random.randint(0, width - 1), random.randint(0, height - 1)), fill=(185, 185, 185))

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    async def create_captcha(self) -> tuple[str, str]:
        captcha_id = uuid.uuid4().hex
        code = self._generate_code()
        normalized_code = self._normalize_code(code)
        try:
            await execute_redis("setex", f"captcha:{captcha_id}", settings.CAPTCHA_TTL_SECONDS, normalized_code)
            await execute_redis("setex", f"captcha_retry:{captcha_id}", settings.CAPTCHA_TTL_SECONDS, 0)
        except Exception as exc:
            logger.warning("[captcha.create] cache_write_failed captcha_id={} error={}", captcha_id, str(exc))
        return captcha_id, self._generate_image_base64(code)

    async def verify_captcha(self, captcha_id: str, captcha_code: str, *, consume: bool = True) -> bool:
        captcha_key = f"captcha:{captcha_id}"
        retry_key = f"captcha_retry:{captcha_id}"
        input_code = self._normalize_code(captcha_code)

        try:
            saved = await execute_redis("get", captcha_key)
            if not saved:
                return False

            retry_count_raw = await execute_redis("get", retry_key)
            retry_count = int(retry_count_raw) if retry_count_raw else 0
            if retry_count >= settings.CAPTCHA_MAX_RETRY:
                await execute_redis("delete", captcha_key)
                await execute_redis("delete", retry_key)
                return False

            saved_code = self._normalize_code(saved)
            is_valid = saved_code == input_code
            if is_valid:
                if consume:
                    await execute_redis("delete", captcha_key)
                    await execute_redis("delete", retry_key)
                return True

            retry_count += 1
            if retry_count >= settings.CAPTCHA_MAX_RETRY:
                await execute_redis("delete", captcha_key)
                await execute_redis("delete", retry_key)
            else:
                ttl = await execute_redis("ttl", captcha_key)
                ttl = ttl if ttl and ttl > 0 else settings.CAPTCHA_TTL_SECONDS
                await execute_redis("setex", retry_key, ttl, retry_count)
            return False
        except Exception as exc:
            logger.warning("[captcha.verify] cache_access_failed captcha_id={} error={}", captcha_id, str(exc))
            return False


captcha_controller = CaptchaController()
