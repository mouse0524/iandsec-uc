from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from datetime import datetime

import httpx

from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.models.admin import SkillKnowConversation, SkillKnowLearningCandidate, SkillKnowMessage, SkillKnowMessageFeedback, SkillKnowPrompt
from app.models.enums import SkillKnowLearningStatus, SkillKnowMessageRole
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client
from app.services.skill_know.prompt_service import skill_know_prompt_service
from app.services.skill_know.retriever import skill_know_retriever
from app.services.skill_know.utils import new_uuid


def event(event_type: str, payload: dict | None = None) -> dict:
    return {"type": event_type, "payload": payload or {}, "ts": int(time.time() * 1000)}


def _status_hint(status_code: int | str) -> str:
    try:
        code = int(status_code)
    except Exception:
        return "请检查网络与模型服务状态。"
    if code == 401:
        return "认证失败：请检查 API Key 是否正确且仍有效。"
    if code == 403:
        return "权限不足：请检查 Key 权限、模型访问范围或账号策略。"
    if code == 404:
        return "资源不存在：请检查 Base URL 与模型名是否正确。"
    if code == 429:
        return "请求过多：请稍后重试，或检查配额/速率限制。"
    if 500 <= code < 600:
        return "模型服务端异常：请稍后重试。"
    return "请检查请求参数、模型配置与网络连通性。"


class SkillKnowChatService:
    async def _conversation(self, conversation_id: int | None, message: str) -> SkillKnowConversation:
        if conversation_id:
            item = await SkillKnowConversation.filter(id=conversation_id).first()
            if item:
                return item
        return await SkillKnowConversation.create(uuid=new_uuid(), title=message[:60])

    async def _prompt(self, key: str, fallback: str) -> str:
        await skill_know_prompt_service.initialize_defaults()
        prompt = await SkillKnowPrompt.filter(key=key, is_active=True).first()
        return prompt.content if prompt else fallback

    def _render_context(self, items: list[dict], max_chars: int) -> str:
        blocks = []
        used = 0
        for idx, item in enumerate(items, start=1):
            content = str(item.get("content") or "")
            if not content:
                continue
            block = "\n".join([
                f"[引用 {idx}]",
                f"标题：{item.get('title') or '-'}",
                f"原文件：{item.get('filename') or '-'}",
                f"章节：{item.get('heading') or '-'}",
                f"匹配分：{item.get('score')}",
                "```markdown",
                content[:2400],
                "```",
            ])
            if used + len(block) > max_chars:
                break
            blocks.append(block)
            used += len(block)
        return "\n\n".join(blocks)

    def _citations(self, items: list[dict]) -> list[dict]:
        return [
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "chunk_uri": item.get("chunk_uri"),
                "title": item.get("title"),
                "filename": item.get("filename"),
                "heading": item.get("heading"),
                "score": item.get("score"),
                "matched_by": item.get("matched_by"),
            }
            for item in items
        ]

    async def _history_messages(self, conversation_id: int, *, limit: int = 12) -> list[dict]:
        rows = await SkillKnowMessage.filter(conversation_id=conversation_id).order_by("-id").limit(limit)
        rows = list(reversed(rows))
        history = []
        for row in rows:
            if row.role not in {SkillKnowMessageRole.USER, SkillKnowMessageRole.ASSISTANT}:
                continue
            history.append({"role": str(row.role), "content": row.content})
        return history

    async def chat(self, message: str, conversation_id: int | None = None) -> dict:
        content = ""
        async for item in self.stream(message, conversation_id=conversation_id):
            if item["type"] == "assistant.delta":
                content += item["payload"].get("content", "")
            if item["type"] == "final":
                return item["payload"]
        return {"content": content}

    async def stream(self, message: str, conversation_id: int | None = None) -> AsyncGenerator[dict, None]:
        start = time.perf_counter()
        timeline: list[dict] = []
        conv = await self._conversation(conversation_id, message)
        user_event = event("user.message", {"content": message, "conversation_id": conv.id})
        timeline.append(user_event)
        yield user_event

        user_msg = await SkillKnowMessage.create(uuid=new_uuid(), conversation_id=conv.id, role=SkillKnowMessageRole.USER, content=message)

        phase = event("phase.changed", {"phase": "retrieving", "label": "检索 Markdown 文档片段"})
        timeline.append(phase)
        yield phase

        context_items = await skill_know_retriever.retrieve_document_chunks(message)
        citations = self._citations(context_items)
        search_event = event("search.results", {"query": message, "items": context_items, "citations": citations, "total": len(context_items)})
        timeline.append(search_event)
        yield search_event

        max_context_chars = int(await skill_know_config_service.get("retrieval_max_context_chars", 128000) or 128000)
        context = self._render_context(context_items, max_chars=max_context_chars)
        system_prompt = await self._prompt("system.chat", "你是 Skill-Know 知识库助手。")
        answer_prompt = await self._prompt("rag.answer", "请基于知识库片段回答用户问题。") if context else await self._prompt("rag.no_context", "当前知识库没有足够依据。")
        security_prompt = await self._prompt("security.expert", "遇到数据安全问题时必须说明风险、权限、审计和回滚建议。")

        history_messages = await self._history_messages(conv.id)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": security_prompt},
            {"role": "system", "content": answer_prompt},
            {"role": "system", "content": f"已检索到的 Markdown 知识库片段：\n{context}" if context else "当前没有检索到相关 Markdown 片段。"},
            *history_messages,
        ]

        llm_start = event("llm.call.started", {"model": await skill_know_config_service.get("llm_chat_model"), "stream": True})
        timeline.append(llm_start)
        yield llm_start

        answer = ""
        try:
            async for chunk in skill_know_openai_client.stream_chat(messages):
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                if not delta:
                    continue
                answer += delta
                yield event("assistant.delta", {"content": delta})
            done = event("llm.call.completed", {"length": len(answer)})
            timeline.append(done)
            yield done
        except httpx.ConnectError as exc:
            logger.warning("[skill_know.chat.stream] network connect error conv_id={} error={}", conv.id, str(exc))
            answer = answer or "网络连接失败，请检查网络设置"
            yield event("assistant.delta", {"content": answer})
            err = event("error", {"message": "网络连接失败，请检查网络设置"})
            timeline.append(err)
            yield err
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response else "unknown"
            hint = _status_hint(status_code)
            answer = answer or f"API错误: {status_code}。{hint}"
            yield event("assistant.delta", {"content": answer})
            err = event("error", {"message": f"API错误: {status_code}", "hint": hint, "status_code": status_code})
            timeline.append(err)
            yield err
        except Exception as exc:
            logger.exception("[skill_know.chat.stream] unexpected error conv_id={} error={}", conv.id, str(exc))
            answer = answer or "服务暂时不可用，请稍后重试"
            yield event("assistant.delta", {"content": answer})
            err = event("error", {"message": "服务暂时不可用，请稍后重试"})
            timeline.append(err)
            yield err

        latency_ms = int((time.perf_counter() - start) * 1000)
        msg = await SkillKnowMessage.create(
            uuid=new_uuid(),
            conversation_id=conv.id,
            role=SkillKnowMessageRole.ASSISTANT,
            content=answer,
            timeline=timeline,
            latency_ms=latency_ms,
            extra_metadata={
                "citations": citations,
                "user_message_id": user_msg.id,
                "model": await skill_know_config_service.get("llm_chat_model"),
            },
        )
        final = event("final", {"conversation_id": conv.id, "message_id": msg.id, "content": answer, "citations": citations, "latency_ms": latency_ms})
        yield final

    async def list_conversations(self, page: int, page_size: int) -> tuple[int, list[dict]]:
        query = SkillKnowConversation.all()
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, [await item.to_dict() for item in rows]

    async def get_conversation(self, conversation_id: int) -> dict:
        conv = await SkillKnowConversation.get(id=conversation_id)
        data = await conv.to_dict()
        messages = await SkillKnowMessage.filter(conversation_id=conversation_id).order_by("id")
        data["messages"] = [await item.to_dict() for item in messages]
        return data

    async def delete_conversation(self, conversation_id: int) -> None:
        await SkillKnowMessageFeedback.filter(conversation_id=conversation_id).delete()
        await SkillKnowMessage.filter(conversation_id=conversation_id).delete()
        await SkillKnowConversation.filter(id=conversation_id).delete()

    async def messages(self, conversation_id: int) -> list[dict]:
        rows = await SkillKnowMessage.filter(conversation_id=conversation_id).order_by("id")
        return [await item.to_dict() for item in rows]

    async def feedback(self, data) -> dict:
        msg = await SkillKnowMessage.get(id=data.message_id)
        user_id = None
        try:
            user_id = CTX_USER_ID.get()
        except Exception:
            pass
        feedback = await SkillKnowMessageFeedback.create(
            message_id=msg.id,
            conversation_id=msg.conversation_id,
            rating=data.rating,
            is_helpful=data.is_helpful,
            reason=data.reason,
            correct_answer=data.correct_answer,
            created_by=user_id,
        )
        if data.is_helpful is False or (data.rating is not None and data.rating <= 2) or data.correct_answer:
            question = ""
            user_message_id = (msg.extra_metadata or {}).get("user_message_id")
            if user_message_id:
                user_msg = await SkillKnowMessage.filter(id=user_message_id).first()
                question = user_msg.content if user_msg else ""
            await SkillKnowLearningCandidate.create(
                question=question or "请根据对话记录补充问题",
                assistant_answer=msg.content,
                feedback_reason=data.reason,
                correct_answer=data.correct_answer,
                source_conversation_id=msg.conversation_id,
                source_message_id=msg.id,
                status=SkillKnowLearningStatus.PENDING,
                candidate_markdown=self._candidate_markdown(question, msg.content, data.reason, data.correct_answer),
                extra_metadata={"feedback_id": feedback.id},
            )
        return await feedback.to_dict()

    async def feedback_list(self, page: int, page_size: int, low_score_only: bool = False) -> tuple[int, list[dict]]:
        query = SkillKnowMessageFeedback.all()
        if low_score_only:
            query = query.filter(rating__lte=2)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, [await item.to_dict() for item in rows]

    async def list_learning_candidates(self, page: int, page_size: int, status: SkillKnowLearningStatus | None = None) -> tuple[int, list[dict]]:
        query = SkillKnowLearningCandidate.all()
        if status:
            query = query.filter(status=status)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, [await item.to_dict() for item in rows]

    async def create_learning_candidate(self, data) -> dict:
        item = await SkillKnowLearningCandidate.create(
            question=data.question,
            assistant_answer=data.assistant_answer,
            feedback_reason=data.feedback_reason,
            correct_answer=data.correct_answer,
            candidate_markdown=data.candidate_markdown or self._candidate_markdown(data.question, data.assistant_answer, data.feedback_reason, data.correct_answer),
        )
        return await item.to_dict()

    async def approve_learning_candidate(self, data) -> dict:
        item = await SkillKnowLearningCandidate.get(id=data.candidate_id)
        item.status = SkillKnowLearningStatus.APPROVED
        if data.candidate_markdown is not None:
            item.candidate_markdown = data.candidate_markdown
        item.reviewed_at = datetime.now()
        try:
            item.reviewed_by = CTX_USER_ID.get()
        except Exception:
            pass
        await item.save()
        return await item.to_dict()

    async def reject_learning_candidate(self, data) -> dict:
        item = await SkillKnowLearningCandidate.get(id=data.candidate_id)
        item.status = SkillKnowLearningStatus.REJECTED
        item.reviewed_at = datetime.now()
        try:
            item.reviewed_by = CTX_USER_ID.get()
        except Exception:
            pass
        await item.save()
        return await item.to_dict()

    def _candidate_markdown(self, question: str | None, answer: str | None, reason: str | None, correct_answer: str | None) -> str:
        return "\n".join([
            "# 待补充知识",
            "",
            "## 问题场景",
            question or "待管理员确认",
            "",
            "## 已知现象",
            reason or "来自对话评分反馈，需管理员补充现象。",
            "",
            "## 建议解决方案",
            correct_answer or answer or "待管理员确认。",
            "",
            "## 风险提示",
            "如涉及数据安全、权限、审计或敏感信息，需安全复核后再入库。",
            "",
            "## 待确认事项",
            "- 产品版本、部署环境、错误日志、影响范围是否完整。",
            "- 解决方案是否已经验证。",
            "",
            "## 来源",
            "对话评分反馈。",
        ])

    async def stats(self, conversation_id: int) -> dict:
        messages = await SkillKnowMessage.filter(conversation_id=conversation_id)
        return {"conversation_id": conversation_id, "stats": {"total_turns": len(messages)}, "has_summary": False}


def sse_encode(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


skill_know_chat_service = SkillKnowChatService()
