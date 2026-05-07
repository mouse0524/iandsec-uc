import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise

from app.models.admin import SkillKnowSystemConfig
from app.settings.config import settings


async def main() -> None:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        item = await SkillKnowSystemConfig.filter(key="retrieval_max_context_chars").first()
        created = False
        updated = False
        current = None

        if not item:
            item = await SkillKnowSystemConfig.create(
                key="retrieval_max_context_chars",
                value=128000,
                group="retrieval",
                description="最大上下文字符数",
                is_sensitive=False,
            )
            created = True
            current = 128000
        else:
            current = item.value.get("__raw") if isinstance(item.value, dict) and "__raw" in item.value else item.value
            try:
                normalized = int(current)
            except Exception:
                normalized = None

            if normalized in {None, 12000}:
                item.value = 128000
                item.group = "retrieval"
                item.description = item.description or "最大上下文字符数"
                item.is_sensitive = False
                await item.save()
                updated = True
                current = 128000

        print({"created": created, "updated": updated, "current": current})
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
