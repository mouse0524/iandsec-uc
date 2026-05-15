from __future__ import annotations

import time
from dataclasses import dataclass

from app.services.skill_know.golden_case_service import skill_know_golden_case_service
from app.services.skill_know.reader_agent.reader_tools import skill_know_reader_tools


@dataclass
class SkillKnowEvalCase:
    question: str
    expected_document_id: int | None = None
    expected_section_id: int | None = None
    expected_heading_contains: str | None = None


class SkillKnowEvalService:
    async def evaluate_case(self, case: SkillKnowEvalCase, *, top_k: int = 8) -> dict:
        started = time.perf_counter()
        items = await skill_know_reader_tools.search_sections(case.question, limit=top_k)
        latency_ms = int((time.perf_counter() - started) * 1000)
        matched_rank = self._matched_rank(case, items)
        return {
            "question": case.question,
            "expected_document_id": case.expected_document_id,
            "expected_section_id": case.expected_section_id,
            "expected_heading_contains": case.expected_heading_contains,
            "matched_rank": matched_rank,
            "top1_hit": matched_rank == 1,
            "top3_hit": bool(matched_rank and matched_rank <= 3),
            "top_k_hit": bool(matched_rank and matched_rank <= top_k),
            "latency_ms": latency_ms,
            "items": items,
        }

    async def evaluate_cases(self, cases: list[SkillKnowEvalCase], *, top_k: int = 8) -> dict:
        results = [await self.evaluate_case(case, top_k=top_k) for case in cases]
        total = len(results)
        if not total:
            return {"total": 0, "top1_accuracy": 0, "top3_accuracy": 0, "top_k_accuracy": 0, "avg_latency_ms": 0, "results": []}
        return {
            "total": total,
            "top1_accuracy": round(sum(1 for item in results if item["top1_hit"]) / total, 4),
            "top3_accuracy": round(sum(1 for item in results if item["top3_hit"]) / total, 4),
            "top_k_accuracy": round(sum(1 for item in results if item["top_k_hit"]) / total, 4),
            "avg_latency_ms": round(sum(item["latency_ms"] for item in results) / total, 2),
            "results": results,
        }

    async def evaluate_golden_cases(self, *, top_k: int = 8) -> dict:
        rows = skill_know_golden_case_service.list_cases(enabled_only=True)
        cases = [
            SkillKnowEvalCase(
                question=row.get("question") or "",
                expected_document_id=row.get("expected_document_id"),
                expected_section_id=row.get("expected_section_id"),
                expected_heading_contains=row.get("expected_heading_contains"),
            )
            for row in rows
            if row.get("question")
        ]
        result = await self.evaluate_cases(cases, top_k=top_k)
        result["case_source"] = str(skill_know_golden_case_service.path)
        return result

    def _matched_rank(self, case: SkillKnowEvalCase, items: list[dict]) -> int | None:
        for index, item in enumerate(items, start=1):
            if case.expected_section_id and int(item.get("section_id") or 0) == case.expected_section_id:
                return index
            if case.expected_document_id and int(item.get("document_id") or 0) != case.expected_document_id:
                continue
            if case.expected_heading_contains:
                heading = " ".join([str(item.get("heading") or ""), str(item.get("heading_path") or "")])
                if case.expected_heading_contains not in heading:
                    continue
            if case.expected_document_id or case.expected_heading_contains:
                return index
        return None


skill_know_eval_service = SkillKnowEvalService()
