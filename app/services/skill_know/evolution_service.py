from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.skill_know import SkillKnowGoldenCaseIn
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.document_service import skill_know_document_service
from app.services.skill_know.eval_service import skill_know_eval_service
from app.services.skill_know.golden_case_service import skill_know_golden_case_service
from app.services.skill_know.knowledge_gap_service import skill_know_knowledge_gap_service
from app.services.skill_know.learning_candidate_service import skill_know_learning_candidate_service


class LearningCandidateImportError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SkillKnowEvolutionService:
    def __init__(
        self,
        report_dir: str | Path | None = None,
        eval_service: Any | None = None,
        config_service: Any | None = None,
        gap_service: Any | None = None,
        golden_case_service: Any | None = None,
        candidate_service: Any | None = None,
        document_service: Any | None = None,
    ) -> None:
        self.report_dir = Path(report_dir or Path("storage") / "skill_know" / "evolution_reports")
        self.eval_service = eval_service or skill_know_eval_service
        self.config_service = config_service or skill_know_config_service
        self.gap_service = gap_service or skill_know_knowledge_gap_service
        self.golden_case_service = golden_case_service or skill_know_golden_case_service
        self.candidate_service = candidate_service or skill_know_learning_candidate_service
        self.document_service = document_service or skill_know_document_service

    async def get_settings(self) -> dict:
        enabled = await self.config_service.get("evolution_daily_eval_enabled", True)
        run_at = await self.config_service.get("evolution_daily_eval_time", "02:10")
        top_k = await self.config_service.get("evolution_daily_eval_top_k", 8)
        return {
            "enabled": self._as_bool(enabled),
            "run_at": self._normalize_run_at(run_at),
            "top_k": self._normalize_top_k(top_k),
        }

    async def save_settings(self, payload: dict) -> dict:
        enabled = self._as_bool(payload.get("enabled", True))
        run_at = self._normalize_run_at(payload.get("run_at", "02:10"))
        top_k = self._normalize_top_k(payload.get("top_k", 8))
        await self.config_service.set(
            "evolution_daily_eval_enabled",
            enabled,
            group="evolution",
            description="是否启用 Skill-Know 自进化每日评测",
        )
        await self.config_service.set(
            "evolution_daily_eval_time",
            run_at,
            group="evolution",
            description="Skill-Know 自进化每日评测时间(HH:MM)",
        )
        await self.config_service.set(
            "evolution_daily_eval_top_k",
            top_k,
            group="evolution",
            description="Skill-Know 自进化每日评测 TopK",
        )
        return {"enabled": enabled, "run_at": run_at, "top_k": top_k}

    async def run_daily_eval_report(self, *, top_k: int = 8) -> dict:
        started_at = self._now()
        report_id = self._report_id(started_at)
        try:
            eval_result = await self.eval_service.evaluate_golden_cases(top_k=top_k)
            report = self._build_success_report(
                report_id=report_id,
                started_at=started_at,
                finished_at=self._now(),
                top_k=top_k,
                eval_result=eval_result,
            )
        except Exception as exc:
            report = self._build_failed_report(
                report_id=report_id,
                started_at=started_at,
                finished_at=self._now(),
                top_k=top_k,
                error_message=str(exc),
            )
        self._save_report(report)
        return report

    def list_reports(self, *, limit: int = 20) -> list[dict]:
        if not self.report_dir.exists():
            return []
        reports = []
        for path in sorted(self.report_dir.glob("*.json"), reverse=True):
            report = self._load_report(path)
            if not report:
                continue
            reports.append(self._summary(report))
            if len(reports) >= limit:
                break
        return reports

    def get_report(self, report_id: str) -> dict | None:
        if not report_id or "/" in report_id or "\\" in report_id:
            return None
        return self._load_report(self.report_dir / f"{report_id}.json")

    def list_knowledge_gaps(self, *, status: str | None = None, limit: int = 200) -> list[dict]:
        return self.gap_service.list_gaps(status=status, limit=limit)

    def update_knowledge_gap_status(self, gap_id: str, *, status: str) -> dict | None:
        if status not in {"pending", "ignored", "resolved"}:
            raise ValueError("invalid gap status")
        return self.gap_service.update_status(gap_id, status=status)

    def convert_gap_to_golden_case(
        self,
        gap_id: str,
        *,
        expected_document_id: int | None = None,
        expected_section_id: int | None = None,
        expected_heading_contains: str | None = None,
    ) -> dict | None:
        gap = self.gap_service.get_gap(gap_id)
        if not gap:
            return None
        golden_case = self.golden_case_service.upsert(
            SkillKnowGoldenCaseIn(
                question=str(gap.get("question") or ""),
                expected_document_id=expected_document_id,
                expected_section_id=expected_section_id,
                expected_heading_contains=expected_heading_contains,
                enabled=True,
            )
        )
        updated_gap = self.gap_service.update_status(
            gap_id,
            status="resolved",
            golden_case_id=golden_case.get("id"),
        )
        return {"gap": updated_gap, "golden_case": golden_case}

    def list_learning_candidates(self, *, status: str | None = None, limit: int = 200) -> list[dict]:
        return self.candidate_service.list_candidates(status=status, limit=limit)

    def create_learning_candidate_from_gap(
        self,
        gap_id: str,
        *,
        title: str | None = None,
        draft_answer: str | None = None,
    ) -> dict | None:
        gap = self.gap_service.get_gap(gap_id)
        if not gap:
            return None
        candidate = self.candidate_service.create_from_gap(
            gap=gap,
            title=title,
            draft_answer=draft_answer,
        )
        updated_gap = self.gap_service.update_status(
            gap_id,
            status=str(gap.get("status") or "pending"),
            learning_candidate_id=candidate.get("id"),
        )
        return {"gap": updated_gap, "candidate": candidate}

    def update_learning_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str,
        review_note: str | None = None,
    ) -> dict | None:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("invalid candidate status")
        return self.candidate_service.update_status(candidate_id, status=status, review_note=review_note)

    def generate_learning_candidate_draft(self, candidate_id: str) -> dict | None:
        return self.candidate_service.generate_markdown_draft(candidate_id)

    async def import_learning_candidate(self, candidate_id: str, *, folder_id: int | None = None) -> dict | None:
        if hasattr(self.candidate_service, "reserve_import"):
            candidate, reason = self.candidate_service.reserve_import(candidate_id)
        else:
            candidate = self.candidate_service.get_candidate(candidate_id)
            if not candidate:
                reason = "not_found"
            elif candidate.get("status") not in {"approved", "drafted"}:
                reason = "invalid_status"
            else:
                reason = None
        if not candidate:
            if reason == "not_found":
                return None
            self._raise_import_error(reason)
        if reason:
            self._raise_import_error(reason)
        content = self.candidate_service.draft_content(candidate_id)
        if not content:
            self._restore_candidate_import_status(candidate_id, candidate)
            raise LearningCandidateImportError(400, "学习候选草稿内容为空，无法入库")
        try:
            document = await self.document_service.create_markdown_document(
                title=str(candidate.get("title") or candidate.get("question") or "学习候选"),
                content=content,
                folder_id=folder_id,
                metadata={
                    "source": "learning_candidate",
                    "candidate_id": candidate_id,
                    "source_gap_id": candidate.get("source_gap_id"),
                },
            )
        except Exception:
            self._restore_candidate_import_status(candidate_id, candidate)
            raise
        updated = self.candidate_service.mark_imported(candidate_id, document_id=int(document["id"]))
        return {"candidate": updated, "document": document}

    def _raise_import_error(self, reason: str | None) -> None:
        if reason == "not_found":
            return
        if reason in {"imported", "importing"}:
            raise LearningCandidateImportError(409, "学习候选正在入库或已入库，请勿重复提交")
        if reason == "invalid_status":
            raise LearningCandidateImportError(409, "学习候选未审核通过，不能入库")
        raise LearningCandidateImportError(400, "学习候选无法入库")

    def _restore_candidate_import_status(self, candidate_id: str, candidate: dict) -> None:
        if hasattr(self.candidate_service, "restore_import_status"):
            self.candidate_service.restore_import_status(
                candidate_id,
                status=str(candidate.get("previous_status") or candidate.get("status") or "approved"),
            )

    def _build_success_report(
        self,
        *,
        report_id: str,
        started_at: str,
        finished_at: str,
        top_k: int,
        eval_result: dict,
    ) -> dict:
        results = [item for item in eval_result.get("results", []) if isinstance(item, dict)]
        low_score_questions = [
            str(item.get("question") or "")
            for item in results
            if not item.get("top_k_hit") and item.get("question")
        ]
        knowledge_gaps = self._upsert_knowledge_gaps(report_id, low_score_questions)
        return {
            "report_id": report_id,
            "task_type": "daily_eval",
            "status": "success",
            "started_at": started_at,
            "finished_at": finished_at,
            "top_k": top_k,
            "metrics": self._metrics(eval_result),
            "case_source": eval_result.get("case_source"),
            "low_score_questions": low_score_questions,
            "knowledge_gaps": knowledge_gaps,
            "next_actions": self._next_actions(low_score_questions),
            "eval_result": eval_result,
        }

    def _build_failed_report(
        self,
        *,
        report_id: str,
        started_at: str,
        finished_at: str,
        top_k: int,
        error_message: str,
    ) -> dict:
        return {
            "report_id": report_id,
            "task_type": "daily_eval",
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "top_k": top_k,
            "metrics": self._metrics({}),
            "case_source": None,
            "low_score_questions": [],
            "knowledge_gaps": {"upserted_count": 0, "items": []},
            "next_actions": [
                {
                    "type": "investigate_eval_failure",
                    "title": "检查每日评测失败原因",
                    "detail": error_message,
                }
            ],
            "error_message": error_message,
            "eval_result": None,
        }

    def _metrics(self, eval_result: dict) -> dict:
        return {
            "total": int(eval_result.get("total") or 0),
            "top1_accuracy": float(eval_result.get("top1_accuracy") or 0),
            "top3_accuracy": float(eval_result.get("top3_accuracy") or 0),
            "top_k_accuracy": float(eval_result.get("top_k_accuracy") or 0),
            "avg_latency_ms": float(eval_result.get("avg_latency_ms") or 0),
        }

    def _next_actions(self, low_score_questions: list[str]) -> list[dict]:
        if not low_score_questions:
            return [
                {
                    "type": "maintain_golden_cases",
                    "title": "继续维护黄金问题",
                    "detail": "本次黄金问题全部命中，建议补充近期高频业务问题，防止评测集老化。",
                }
            ]
        return [
            {
                "type": "knowledge_gap",
                "title": "沉淀未命中问题",
                "detail": question,
            }
            for question in low_score_questions
        ]

    def _upsert_knowledge_gaps(self, report_id: str, questions: list[str]) -> dict:
        items = []
        for question in questions:
            try:
                items.append(self.gap_service.upsert_from_eval_miss(question=question, report_id=report_id))
            except Exception:
                continue
        return {"upserted_count": len(items), "items": items}

    def _summary(self, report: dict) -> dict:
        return {
            "report_id": report.get("report_id"),
            "task_type": report.get("task_type"),
            "status": report.get("status"),
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "top_k": report.get("top_k"),
            "metrics": report.get("metrics") or {},
            "low_score_count": len(report.get("low_score_questions") or []),
        }

    def _save_report(self, report: dict) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        path = self.report_dir / f"{report['report_id']}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_report(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _now(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")

    def _report_id(self, started_at: str) -> str:
        return started_at.replace(":", "").replace("+", "-").replace(".", "-")

    def _as_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}

    def _normalize_run_at(self, value) -> str:
        try:
            hour_text, minute_text = str(value or "").strip().split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("run_at out of range")
            return f"{hour:02d}:{minute:02d}"
        except Exception:
            return "02:10"

    def _normalize_top_k(self, value) -> int:
        try:
            parsed = int(value)
        except Exception:
            return 8
        return min(20, max(1, parsed))


skill_know_evolution_service = SkillKnowEvolutionService()
