import asyncio
import shutil
from pathlib import Path

from tortoise import Tortoise

from app.models.admin import (
    SkillKnowContextRelation,
    SkillKnowConversation,
    SkillKnowDocument,
    SkillKnowDocumentChunk,
    SkillKnowFolder,
    SkillKnowLearningCandidate,
    SkillKnowMessage,
    SkillKnowMessageFeedback,
    SkillKnowPrompt,
    SkillKnowSystemConfig,
    SkillKnowUploadTask,
    SkillKnowVectorIndex,
)
from app.services.skill_know.prompt_service import skill_know_prompt_service
from app.settings import settings


async def reset_skill_know() -> None:
    await Tortoise.init(config=settings.TORTOISE_ORM)
    try:
        for model in [
            SkillKnowMessageFeedback,
            SkillKnowLearningCandidate,
            SkillKnowMessage,
            SkillKnowConversation,
            SkillKnowContextRelation,
            SkillKnowVectorIndex,
            SkillKnowDocumentChunk,
            SkillKnowDocument,
            SkillKnowUploadTask,
            SkillKnowFolder,
            SkillKnowPrompt,
            SkillKnowSystemConfig,
        ]:
            await model.all().delete()

        for path in [
            Path(settings.BASE_DIR) / "storage" / "skill_know" / "chroma",
            Path(settings.UPLOAD_DIR) / "skill_know",
        ]:
            if path.exists():
                shutil.rmtree(path)

        await skill_know_prompt_service.initialize_defaults()
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(reset_skill_know())
