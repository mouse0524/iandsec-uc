from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


class SkillKnowKnowledgeGapService:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path("storage") / "skill_know" / "knowledge_gaps.json")
        self._lock = threading.RLock()

    def list_gaps(self, *, status: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._load()
            if status:
                rows = [item for item in rows if item.get("status") == status]
            rows.sort(
                key=lambda item: (
                    item.get("priority") or 0,
                    item.get("occurrences") or 0,
                    item.get("updated_at") or "",
                ),
                reverse=True,
            )
            return rows[:limit]

    def get_gap(self, gap_id: str) -> dict | None:
        with self._lock:
            for row in self._load():
                if row.get("id") == gap_id:
                    return row
        return None

    def update_status(
        self,
        gap_id: str,
        *,
        status: str,
        resolved_by_document_id: int | None = None,
        golden_case_id: str | None = None,
        learning_candidate_id: str | None = None,
    ) -> dict | None:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != gap_id:
                    continue
                row["status"] = status
                row["updated_at"] = now
                if resolved_by_document_id is not None:
                    row["resolved_by_document_id"] = resolved_by_document_id
                if golden_case_id:
                    row["golden_case_id"] = golden_case_id
                if learning_candidate_id:
                    row["learning_candidate_id"] = learning_candidate_id
                self._save(rows)
                return row
        return None

    def upsert_from_eval_miss(self, *, question: str, report_id: str, failure_type: str = "retrieval_miss") -> dict:
        normalized = self._normalize_question(question)
        if not normalized:
            raise ValueError("question is required")
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if self._normalize_question(row.get("question")) == normalized:
                    row["occurrences"] = int(row.get("occurrences") or 0) + 1
                    row["updated_at"] = now
                    row["last_report_id"] = report_id
                    row["status"] = row.get("status") or "pending"
                    row["failure_type"] = row.get("failure_type") or failure_type
                    self._save(rows)
                    return row
            row = {
                "id": f"gap-{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]}",
                "question": question.strip(),
                "failure_type": failure_type,
                "expected_topic": "",
                "status": "pending",
                "priority": 50,
                "occurrences": 1,
                "first_report_id": report_id,
                "last_report_id": report_id,
                "resolved_by_document_id": None,
                "learning_candidate_id": None,
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            self._save(rows)
            return row

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _save(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.tmp")
        temp_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.path)

    def _normalize_question(self, value) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _now(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


skill_know_knowledge_gap_service = SkillKnowKnowledgeGapService()
