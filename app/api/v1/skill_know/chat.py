from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas.base import Success, SuccessExtra
from app.models.enums import SkillKnowLearningStatus
from app.schemas.skill_know import SkillKnowChatIn, SkillKnowLearningCandidateIn, SkillKnowLearningReviewIn, SkillKnowMessageFeedbackIn
from app.services.skill_know.chat_service import skill_know_chat_service, sse_encode

router = APIRouter()


@router.post("", summary="非流式对话")
async def chat(payload: SkillKnowChatIn):
    return Success(data=await skill_know_chat_service.chat(payload.message, conversation_id=payload.conversation_id))


@router.post("/stream", summary="流式对话")
async def chat_stream(payload: SkillKnowChatIn):
    async def generate():
        async for item in skill_know_chat_service.stream(payload.message, conversation_id=payload.conversation_id):
            yield sse_encode(item)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/agent/stream", summary="Agent时间线流式对话")
async def chat_agent_stream(payload: SkillKnowChatIn):
    async def generate():
        async for item in skill_know_chat_service.stream(payload.message, conversation_id=payload.conversation_id):
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


@router.get("/conversations/messages", summary="会话消息")
async def get_messages(conversation_id: int = Query(...)):
    return Success(data=await skill_know_chat_service.messages(conversation_id))


@router.get("/conversations/stats", summary="会话统计")
async def get_stats(conversation_id: int = Query(...)):
    return Success(data=await skill_know_chat_service.stats(conversation_id))


@router.post("/messages/feedback", summary="提交消息评分")
async def feedback_message(payload: SkillKnowMessageFeedbackIn):
    return Success(data=await skill_know_chat_service.feedback(payload))


@router.get("/feedback/list", summary="评分列表")
async def feedback_list(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), low_score_only: bool = Query(False)):
    total, rows = await skill_know_chat_service.feedback_list(page, page_size, low_score_only=low_score_only)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/learning/candidates", summary="学习候选列表")
async def learning_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: SkillKnowLearningStatus | None = Query(None),
):
    total, rows = await skill_know_chat_service.list_learning_candidates(page, page_size, status=status)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.post("/learning/candidates/create", summary="创建学习候选")
async def create_learning_candidate(payload: SkillKnowLearningCandidateIn):
    return Success(data=await skill_know_chat_service.create_learning_candidate(payload))


@router.post("/learning/candidates/approve", summary="通过学习候选")
async def approve_learning_candidate(payload: SkillKnowLearningReviewIn):
    return Success(data=await skill_know_chat_service.approve_learning_candidate(payload))


@router.post("/learning/candidates/reject", summary="拒绝学习候选")
async def reject_learning_candidate(payload: SkillKnowLearningReviewIn):
    return Success(data=await skill_know_chat_service.reject_learning_candidate(payload))
