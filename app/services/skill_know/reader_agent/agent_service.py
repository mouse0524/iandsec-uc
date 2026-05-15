from __future__ import annotations

import re
import time
from collections.abc import AsyncGenerator

import httpx

from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.models.admin import SkillKnowConversation, SkillKnowMessage
from app.models.enums import SkillKnowMessageRole
from app.services.skill_know.openai_client import skill_know_openai_client
from app.services.skill_know.reader_agent.evidence_quality import skill_know_evidence_quality_service
from app.services.skill_know.reader_agent.reader_tools import Evidence, skill_know_reader_tools
from app.services.skill_know.utils import new_uuid, preview_text


def reader_event(event_type: str, payload: dict | None = None) -> dict:
    return {"type": event_type, "payload": payload or {}, "ts": int(time.time() * 1000)}


class SkillKnowReaderAgentService:
    MAX_SECTIONS = 4
    MAX_EVIDENCE_CHARS = 16000
    MAX_HISTORY_MESSAGES = 6
    MAX_HISTORY_CHARS = 6000
    NO_EVIDENCE_MARKERS = ("当前知识库没有找到足够依据", "建议补充", "原始手册章节")

    async def _conversation(self, conversation_id: int | None, message: str) -> SkillKnowConversation:
        owner_id = CTX_USER_ID.get()
        if conversation_id:
            item = await SkillKnowConversation.filter(id=conversation_id, owner_id=owner_id).first()
            if item:
                return item
        return await SkillKnowConversation.create(uuid=new_uuid(), title=message[:60], owner_id=owner_id)

    async def stream(self, message: str, conversation_id: int | None = None) -> AsyncGenerator[dict, None]:
        start = time.perf_counter()
        timeline: list[dict] = []
        conv = await self._conversation(conversation_id, message)
        history_context = await self._history_context(conv.id)
        search_query = self._search_query(message, history_context)

        user_event = reader_event("user.message", {"content": message, "conversation_id": conv.id})
        timeline.append(user_event)
        yield user_event
        user_msg = await SkillKnowMessage.create(
            uuid=new_uuid(),
            conversation_id=conv.id,
            role=SkillKnowMessageRole.USER,
            content=message,
        )

        phase = reader_event("phase.changed", {"phase": "searching_sections", "label": "检索文档章节"})
        timeline.append(phase)
        yield phase

        candidates = await skill_know_reader_tools.search_sections(search_query, limit=8)
        search_event = reader_event(
            "reader.sections",
            {"query": search_query, "items": candidates, "total": len(candidates)},
        )
        timeline.append(search_event)
        yield search_event

        evidence: list[Evidence] = []
        used_chars = 0
        for candidate in candidates[: self.MAX_SECTIONS]:
            item = await skill_know_reader_tools.read_section(
                candidate["section_id"],
                evidence_id=f"ev-{len(evidence) + 1}",
            )
            if not item:
                continue
            if used_chars + len(item.text) > self.MAX_EVIDENCE_CHARS and evidence:
                continue
            evidence.append(item)
            used_chars += len(item.text)
            read_event = reader_event("reader.evidence", self._evidence_payload(item))
            timeline.append(read_event)
            yield read_event

        citations = self._citations(evidence)
        evidence_quality = skill_know_evidence_quality_service.evaluate(message, candidates, len(evidence))
        context = self._render_evidence(evidence)
        answer = ""
        if not evidence:
            answer = self._no_evidence_answer(message)
            yield reader_event("assistant.delta", {"content": answer})
        elif not evidence_quality.sufficient:
            answer = self._weak_evidence_answer(message, evidence_quality.reasons)
            yield reader_event("assistant.delta", {"content": answer})
        else:
            phase = reader_event("phase.changed", {"phase": "answering", "label": "基于原文生成回答"})
            timeline.append(phase)
            yield phase
            messages = self._messages(message, context, history_context=history_context)
            try:
                async for chunk in skill_know_openai_client.stream_chat(messages):
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                    if not delta:
                        continue
                    answer += delta
                    yield reader_event("assistant.delta", {"content": delta})
            except (httpx.ConnectError, httpx.ConnectTimeout):
                answer = "模型服务连接失败。系统已完成文档读取，但暂时无法生成最终回答，请稍后重试。"
                yield reader_event("assistant.delta", {"content": answer})
            except Exception as exc:
                logger.exception("[skill_know.reader_agent.answer.failed] conv_id={} error={}", conv.id, str(exc))
                answer = "生成回答失败。系统已完成文档读取，请稍后重试。"
                yield reader_event("assistant.delta", {"content": answer})

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
                "mode": "document_reader_agent",
                "history_used": bool(history_context),
                "search_query": search_query,
                "evidence_quality": {
                    "sufficient": evidence_quality.sufficient,
                    "score": evidence_quality.score,
                    "reasons": evidence_quality.reasons,
                },
            },
        )
        yield reader_event(
            "final",
            {
                "conversation_id": conv.id,
                "message_id": msg.id,
                "content": answer,
                "citations": citations,
                "latency_ms": latency_ms,
            },
        )

    def _evidence_payload(self, item: Evidence) -> dict:
        return {
            "evidence_id": item.evidence_id,
            "document_id": item.document_id,
            "section_id": item.section_id,
            "title": item.title,
            "heading_path": item.heading_path,
            "line_range": [item.start_line, item.end_line],
            "preview": preview_text(item.text, 220),
        }

    def _render_evidence(self, evidence: list[Evidence]) -> str:
        return "\n\n".join(item.to_context_block() for item in evidence)

    async def _history_context(self, conversation_id: int) -> str:
        rows = (
            await SkillKnowMessage.filter(conversation_id=conversation_id)
            .filter(role__in=[SkillKnowMessageRole.USER, SkillKnowMessageRole.ASSISTANT])
            .order_by("-id")
            .limit(self.MAX_HISTORY_MESSAGES)
        )
        rows = list(reversed(rows))
        if not rows:
            return ""
        blocks = []
        used = 0
        for row in rows:
            content = preview_text(row.content, 1200)
            if not content:
                continue
            role = "用户" if row.role == SkillKnowMessageRole.USER else "助手"
            block = f"{role}：{content}"
            if used + len(block) > self.MAX_HISTORY_CHARS and blocks:
                break
            blocks.append(block)
            used += len(block)
        return "\n\n".join(blocks)

    def _search_query(self, question: str, history_context: str) -> str:
        current = self._clean_search_text(question)
        history_user_questions = self._history_user_questions(history_context)
        if not history_user_questions:
            return current
        return "\n".join([*history_user_questions[-2:], current])

    def _history_user_questions(self, history_context: str) -> list[str]:
        questions = []
        for block in re.split(r"\n+", history_context or ""):
            text = block.strip()
            if not text.startswith("用户："):
                continue
            value = self._clean_search_text(text.removeprefix("用户："))
            if value:
                questions.append(value)
        return questions

    def _clean_search_text(self, text: str) -> str:
        value = str(text or "")
        for marker in self.NO_EVIDENCE_MARKERS:
            value = value.replace(marker, " ")
        value = re.sub(r"问题：.*", " ", value)
        value = re.sub(r"建议补充：.*", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _messages(self, question: str, evidence_context: str, *, history_context: str = "") -> list[dict]:
        user_parts = []
        if history_context:
            user_parts.extend(["## 会话历史上下文", history_context])
        user_parts.extend(["## 当前用户问题", question, "## 内部原文依据", evidence_context])
        return [
            {
                "role": "system",
                "content": (
                    "你是企业技术支持文档阅读助手。只能根据“内部原文依据”回答，不要使用通用经验、外部知识或历史回答补充事实。"
                    "如果用户是追问，可以用会话历史上下文理解代词、上文主题和省略信息，但最终结论仍必须由内部原文依据支持。"
                    "回答要像技术支持人员写给客户的说明，格式清晰、自然、可执行。"
                    "不要在正文中出现内部检索字段、内部编号、证据编号、当前证据这类系统调试信息。"
                    "引用只用自然语言表达，例如：依据《文档名》章节“章节名”第 10-20 行。"
                    "不要大段摘抄原文；需要引用时只保留短句，并把操作步骤整理成自己的话。"
                    "如果资料不足，直接说“当前知识库没有找到足够依据回答该问题”，再说明建议补充的信息；不要输出内部证据编号。"
                ),
            },
            {
                "role": "user",
                "content": "\n\n".join(user_parts),
            },
        ]

    def _citations(self, evidence: list[Evidence]) -> list[dict]:
        return [
            {
                "evidence_id": item.evidence_id,
                "document_id": item.document_id,
                "section_id": item.section_id,
                "title": item.title,
                "heading": item.heading_path,
                "line_range": [item.start_line, item.end_line],
                "matched_by": "document_reader",
            }
            for item in evidence
        ]

    def _no_evidence_answer(self, question: str) -> str:
        return "\n".join(
            [
                "当前知识库没有找到足够依据回答该问题。",
                "",
                f"问题：{question}",
                "",
                "建议补充：对应产品版本、模块名称、完整操作路径、截图或原始手册章节。",
            ]
        )

    def _weak_evidence_answer(self, question: str, reasons: list[str]) -> str:
        reason_text = "；".join(reasons) if reasons else "检索结果不足以支撑完整回答"
        return "\n".join(
            [
                "当前知识库没有找到足够依据回答该问题。",
                "",
                f"问题：{question}",
                "",
                f"原因：{reason_text}",
                "",
                "建议补充：对应产品版本、模块名称、完整操作路径、截图或原始手册章节。",
            ]
        )


skill_know_reader_agent_service = SkillKnowReaderAgentService()
