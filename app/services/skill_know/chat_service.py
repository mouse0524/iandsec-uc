from __future__ import annotations

import json

from fastapi import HTTPException
from tortoise.functions import Max

from app.core.ctx import CTX_USER_ID
from app.models.admin import SkillKnowConversation, SkillKnowMessage, User
from app.models.enums import SkillKnowMessageRole
from app.schemas.skill_know import SkillKnowMessageFeedbackIn
from app.services.skill_know.utils import preview_text


class SkillKnowChatService:
    async def _is_superuser(self) -> bool:
        try:
            user_id = CTX_USER_ID.get()
        except Exception:
            return False
        user = await User.filter(id=user_id).first()
        return bool(user and user.is_superuser)

    async def list_conversations(self, page: int, page_size: int) -> tuple[int, list[dict]]:
        if await self._is_superuser():
            query = SkillKnowConversation.all()
        else:
            query = SkillKnowConversation.filter(owner_id=CTX_USER_ID.get())
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        conversation_ids = [item.id for item in rows]
        owner_ids = [item.owner_id for item in rows if item.owner_id]
        owners = {}
        if owner_ids:
            owner_rows = await User.filter(id__in=sorted(set(owner_ids)))
            owners = {item.id: item for item in owner_rows}
        last_messages = {}
        if conversation_ids:
            latest_rows = (
                await SkillKnowMessage.filter(conversation_id__in=conversation_ids)
                .group_by("conversation_id")
                .annotate(last_id=Max("id"))
                .values("conversation_id", "last_id")
            )
            last_ids = [row["last_id"] for row in latest_rows if row.get("last_id")]
            if last_ids:
                messages = await SkillKnowMessage.filter(id__in=last_ids)
                last_messages = {message.conversation_id: message for message in messages}
        result = []
        for item in rows:
            data = await item.to_dict()
            owner = owners.get(item.owner_id)
            data["owner_name"] = (owner.alias or owner.username) if owner else "-"
            data["owner_username"] = owner.username if owner else ""
            last_message = last_messages.get(item.id)
            if last_message:
                data["last_message_preview"] = preview_text(last_message.content, 72)
                data["last_message_role"] = str(last_message.role)
            else:
                data["last_message_preview"] = ""
                data["last_message_role"] = ""
            result.append(data)
        return total, result

    async def get_conversation(self, conversation_id: int) -> dict:
        if await self._is_superuser():
            conv = await SkillKnowConversation.get(id=conversation_id)
        else:
            conv = await SkillKnowConversation.get(id=conversation_id, owner_id=CTX_USER_ID.get())
        data = await conv.to_dict()
        owner = await User.filter(id=conv.owner_id).first() if conv.owner_id else None
        data["owner_name"] = (owner.alias or owner.username) if owner else "-"
        data["owner_username"] = owner.username if owner else ""
        messages = await SkillKnowMessage.filter(conversation_id=conversation_id).order_by("id")
        data["messages"] = [await item.to_dict() for item in messages]
        return data

    async def delete_conversation(self, conversation_id: int) -> None:
        exists = await SkillKnowConversation.filter(id=conversation_id, owner_id=CTX_USER_ID.get()).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="会话不存在")
        await SkillKnowMessage.filter(conversation_id=conversation_id).delete()
        await SkillKnowConversation.filter(id=conversation_id).delete()

    async def feedback(self, payload: SkillKnowMessageFeedbackIn) -> dict:
        query = SkillKnowMessage.filter(id=payload.message_id, role=SkillKnowMessageRole.ASSISTANT)
        if not await self._is_superuser():
            conversations = await SkillKnowConversation.filter(owner_id=CTX_USER_ID.get()).values_list("id", flat=True)
            query = query.filter(conversation_id__in=list(conversations))
        message = await query.first()
        if not message:
            raise HTTPException(status_code=404, detail="消息不存在")
        metadata = dict(message.extra_metadata or {})
        feedback = {
            "rating": payload.rating,
            "reason": payload.reason or "",
            "note": payload.note or "",
            "user_id": CTX_USER_ID.get(),
        }
        metadata["feedback"] = feedback
        message.extra_metadata = metadata
        await message.save(update_fields=["extra_metadata", "updated_at"])
        return {"message_id": message.id, "feedback": feedback}


def sse_encode(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


skill_know_chat_service = SkillKnowChatService()
