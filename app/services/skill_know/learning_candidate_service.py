from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


class SkillKnowLearningCandidateService:
    def __init__(self, path: str | Path | None = None, draft_dir: str | Path | None = None) -> None:
        self.path = Path(path or Path("storage") / "skill_know" / "learning_candidates.json")
        self.draft_dir = Path(draft_dir or Path("storage") / "skill_know" / "learning_drafts")
        self._lock = threading.RLock()

    def list_candidates(self, *, status: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._load()
            if status:
                rows = [item for item in rows if item.get("status") == status]
            rows.sort(
                key=lambda item: (
                    item.get("priority") or 0,
                    item.get("updated_at") or "",
                ),
                reverse=True,
            )
            return rows[:limit]

    def get_candidate(self, candidate_id: str) -> dict | None:
        with self._lock:
            for row in self._load():
                if row.get("id") == candidate_id:
                    return row
        return None

    def create_from_gap(
        self,
        *,
        gap: dict,
        title: str | None = None,
        draft_answer: str | None = None,
        source: str = "knowledge_gap",
    ) -> dict:
        gap_id = str(gap.get("id") or "")
        question = str(gap.get("question") or "").strip()
        if not gap_id or not question:
            raise ValueError("gap id and question are required")

        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("source_gap_id") == gap_id and row.get("status") in {"pending", "approved"}:
                    row["updated_at"] = now
                    if draft_answer is not None:
                        row["draft_answer"] = draft_answer
                    if title:
                        row["title"] = title.strip()
                    self._save(rows)
                    return row

            normalized = f"{gap_id}:{question}".lower()
            row = {
                "id": f"candidate-{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]}",
                "title": (title or question[:80]).strip(),
                "question": question,
                "draft_answer": (draft_answer or "").strip(),
                "source": source,
                "source_gap_id": gap_id,
                "status": "pending",
                "priority": int(gap.get("priority") or 50),
                "review_note": "",
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            self._save(rows)
            return row

    def update_status(self, candidate_id: str, *, status: str, review_note: str | None = None) -> dict | None:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != candidate_id:
                    continue
                row["status"] = status
                row["updated_at"] = now
                if review_note is not None:
                    row["review_note"] = review_note.strip()
                self._save(rows)
                return row
        return None

    def generate_markdown_draft(self, candidate_id: str) -> dict | None:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != candidate_id:
                    continue
                content = self._markdown_content(row)
                self.draft_dir.mkdir(parents=True, exist_ok=True)
                path = self.draft_dir / f"{candidate_id}.md"
                self._write_text_atomic(path, content)
                row["draft_path"] = str(path)
                if row.get("status") == "approved":
                    row["status"] = "drafted"
                row["updated_at"] = now
                self._save(rows)
                return row
        return None

    def reserve_import(self, candidate_id: str) -> tuple[dict | None, str | None]:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != candidate_id:
                    continue
                status = row.get("status")
                if status == "imported":
                    return None, "imported"
                if status == "importing":
                    return None, "importing"
                if status not in {"approved", "drafted"}:
                    return None, "invalid_status"
                previous_status = str(status)
                row["status"] = "importing"
                row["import_started_at"] = now
                row["updated_at"] = now
                self._save(rows)
                reserved = dict(row)
                reserved["previous_status"] = previous_status
                return reserved, None
        return None, "not_found"

    def restore_import_status(self, candidate_id: str, *, status: str) -> dict | None:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != candidate_id:
                    continue
                if row.get("status") == "importing":
                    row["status"] = status
                    row["updated_at"] = now
                    self._save(rows)
                return row
        return None

    def mark_imported(self, candidate_id: str, *, document_id: int) -> dict | None:
        with self._lock:
            rows = self._load()
            now = self._now()
            for row in rows:
                if row.get("id") != candidate_id:
                    continue
                row["status"] = "imported"
                row["document_id"] = document_id
                row["updated_at"] = now
                self._save(rows)
                return row
        return None

    def draft_content(self, candidate_id: str) -> str | None:
        with self._lock:
            row = self.get_candidate(candidate_id)
            if not row:
                return None
            draft_path = row.get("draft_path")
            if draft_path and Path(draft_path).is_file():
                try:
                    return Path(draft_path).read_text(encoding="utf-8")
                except Exception:
                    pass
            return self._markdown_content(row)

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
        self._write_text_atomic(self.path, json.dumps(rows, ensure_ascii=False, indent=2))

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)

    def _markdown_content(self, row: dict) -> str:
        title = str(row.get("title") or row.get("question") or "学习候选").strip()
        question = str(row.get("question") or "").strip()
        draft_answer = str(row.get("draft_answer") or "").strip()
        lines = [
            f"# {title}",
            "",
            "## 触发问题",
            "",
            question or "-",
            "",
            "## 建议答案",
            "",
            draft_answer or "请补充标准答案。",
            "",
            "## 审核信息",
            "",
            f"- 来源: {row.get('source') or 'knowledge_gap'}",
            f"- 来源缺口: {row.get('source_gap_id') or '-'}",
            f"- 候选 ID: {row.get('id') or '-'}",
        ]
        return "\n".join(lines).rstrip() + "\n"

    def _now(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


skill_know_learning_candidate_service = SkillKnowLearningCandidateService()
