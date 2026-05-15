from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas.base import Success, SuccessExtra
from app.schemas.skill_know import SkillKnowChatIn, SkillKnowMessageFeedbackIn
from app.services.skill_know.chat_job_service import skill_know_chat_job_service
from app.services.skill_know.chat_service import skill_know_chat_service, sse_encode

router = APIRouter()


@router.post("/agent/stream", summary="Agent 时间线流式对话")
async def chat_agent_stream(payload: SkillKnowChatIn):
    async def generate():
        async for item in skill_know_chat_job_service.stream_started_job(payload.message, conversation_id=payload.conversation_id):
            yield sse_encode(item)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations", summary="会话列表")
async def list_conversations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    total, rows = await skill_know_chat_service.list_conversations(page, page_size)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/conversations/get", summary="会话详情")
async def get_conversation(conversation_id: int = Query(...)):
    return Success(data=await skill_know_chat_service.get_conversation(conversation_id))


@router.delete("/conversations/delete", summary="删除会话")
async def delete_conversation(conversation_id: int = Query(...)):
    await skill_know_chat_service.delete_conversation(conversation_id)
    return Success(msg="删除成功")


@router.post("/messages/feedback", summary="记录回答反馈")
async def feedback_message(payload: SkillKnowMessageFeedbackIn):
    return Success(data=await skill_know_chat_service.feedback(payload))
