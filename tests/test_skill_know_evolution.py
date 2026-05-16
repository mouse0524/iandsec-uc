from __future__ import annotations

import json

import anyio
import pytest

from app.services.skill_know.evolution_service import LearningCandidateImportError, SkillKnowEvolutionService
from app.services.skill_know.knowledge_gap_service import SkillKnowKnowledgeGapService
from app.services.skill_know.learning_candidate_service import SkillKnowLearningCandidateService


class FakeEvalService:
    async def evaluate_golden_cases(self, *, top_k: int = 8) -> dict:
        return {
            "total": 2,
            "top1_accuracy": 0.5,
            "top3_accuracy": 1.0,
            "top_k_accuracy": 1.0,
            "avg_latency_ms": 12.5,
            "results": [
                {
                    "question": "Question A",
                    "matched_rank": 1,
                    "top1_hit": True,
                    "top3_hit": True,
                    "top_k_hit": True,
                    "latency_ms": 10,
                },
                {
                    "question": "Question B",
                    "matched_rank": None,
                    "top1_hit": False,
                    "top3_hit": False,
                    "top_k_hit": False,
                    "latency_ms": 15,
                },
            ],
            "case_source": "storage/skill_know/golden_cases.json",
        }


class FakeConfigService:
    def __init__(self):
        self.values = {
            "evolution_daily_eval_enabled": True,
            "evolution_daily_eval_time": "02:10",
            "evolution_daily_eval_top_k": 8,
        }

    async def get(self, key: str, default=None):
        return self.values.get(key, default)

    async def set(self, key: str, value, *, group: str = "llm", description: str | None = None):
        self.values[key] = value.get("__raw") if isinstance(value, dict) and "__raw" in value else value
        return {"key": key, "value": value, "group": group, "description": description}


class FakeGoldenCaseService:
    def __init__(self):
        self.rows = []

    def upsert(self, payload):
        data = payload.model_dump()
        data["id"] = data.get("id") or "case-from-gap"
        self.rows.append(data)
        return data


class FakeDocumentService:
    def __init__(self):
        self.created_documents = []

    async def create_markdown_document(self, *, title: str, content: str, folder_id=None, metadata=None):
        await anyio.sleep(0)
        document = {
            "id": 123 + len(self.created_documents),
            "title": title,
            "content": content,
            "folder_id": folder_id,
            "extra_metadata": metadata or {},
        }
        self.created_documents.append(document)
        return document


class FailingDocumentService:
    async def create_markdown_document(self, *, title: str, content: str, folder_id=None, metadata=None):
        raise RuntimeError("document create failed")


@pytest.mark.anyio
async def test_run_daily_eval_report_persists_summary(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
    )

    report = await service.run_daily_eval_report(top_k=5)

    assert report["task_type"] == "daily_eval"
    assert report["status"] == "success"
    assert report["metrics"] == {
        "total": 2,
        "top1_accuracy": 0.5,
        "top3_accuracy": 1.0,
        "top_k_accuracy": 1.0,
        "avg_latency_ms": 12.5,
    }
    assert report["low_score_questions"] == ["Question B"]
    assert report["next_actions"][0]["type"] == "knowledge_gap"
    assert report["knowledge_gaps"]["upserted_count"] == 1
    assert report["report_id"]

    saved_path = tmp_path / "reports" / f"{report['report_id']}.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8"))["report_id"] == report["report_id"]

    gaps = gap_service.list_gaps()
    assert len(gaps) == 1
    assert gaps[0]["question"] == "Question B"
    assert gaps[0]["status"] == "pending"
    assert gaps[0]["occurrences"] == 1


@pytest.mark.anyio
async def test_list_reports_returns_newest_first(tmp_path):
    service = SkillKnowEvolutionService(report_dir=tmp_path, eval_service=FakeEvalService())
    first = await service.run_daily_eval_report()
    second = await service.run_daily_eval_report()

    reports = service.list_reports()

    assert [item["report_id"] for item in reports] == [second["report_id"], first["report_id"]]
    assert service.get_report(first["report_id"])["report_id"] == first["report_id"]


@pytest.mark.anyio
async def test_save_settings_normalizes_values(tmp_path):
    config = FakeConfigService()
    service = SkillKnowEvolutionService(report_dir=tmp_path, eval_service=FakeEvalService(), config_service=config)

    settings = await service.save_settings({"enabled": False, "run_at": "25:99", "top_k": 99})

    assert settings == {"enabled": False, "run_at": "02:10", "top_k": 20}
    assert await service.get_settings() == settings


def test_gap_status_and_convert_to_golden_case(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    golden_case_service = FakeGoldenCaseService()
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        golden_case_service=golden_case_service,
    )
    gap = gap_service.upsert_from_eval_miss(question="Question C", report_id="report-1")

    ignored = service.update_knowledge_gap_status(gap["id"], status="ignored")
    converted = service.convert_gap_to_golden_case(gap["id"], expected_heading_contains="Topic C")

    assert ignored["status"] == "ignored"
    assert converted["gap"]["status"] == "resolved"
    assert converted["gap"]["golden_case_id"] == "case-from-gap"
    assert converted["golden_case"]["question"] == "Question C"
    assert converted["golden_case"]["expected_heading_contains"] == "Topic C"


def test_gap_to_learning_candidate_review_flow(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    candidate_service = SkillKnowLearningCandidateService(path=tmp_path / "candidates.json")
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        candidate_service=candidate_service,
    )
    gap = gap_service.upsert_from_eval_miss(question="Question D", report_id="report-1")

    result = service.create_learning_candidate_from_gap(
        gap["id"],
        title="Candidate D",
        draft_answer="Draft answer D",
    )
    approved = service.update_learning_candidate_status(
        result["candidate"]["id"],
        status="approved",
        review_note="looks good",
    )

    assert result["gap"]["learning_candidate_id"] == result["candidate"]["id"]
    assert result["candidate"]["title"] == "Candidate D"
    assert result["candidate"]["draft_answer"] == "Draft answer D"
    assert result["candidate"]["status"] == "pending"
    assert approved["status"] == "approved"
    assert approved["review_note"] == "looks good"
    assert service.list_learning_candidates()[0]["id"] == result["candidate"]["id"]


def test_learning_candidate_status_endpoint_states_are_review_only(tmp_path):
    candidate_service = SkillKnowLearningCandidateService(path=tmp_path / "candidates.json")
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        candidate_service=candidate_service,
    )

    with pytest.raises(ValueError):
        service.update_learning_candidate_status("candidate-1", status="drafted")

    with pytest.raises(ValueError):
        service.update_learning_candidate_status("candidate-1", status="imported")


@pytest.mark.anyio
async def test_learning_candidate_draft_and_import(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    candidate_service = SkillKnowLearningCandidateService(
        path=tmp_path / "candidates.json",
        draft_dir=tmp_path / "drafts",
    )
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        candidate_service=candidate_service,
        document_service=FakeDocumentService(),
    )
    gap = gap_service.upsert_from_eval_miss(question="Question E", report_id="report-1")
    result = service.create_learning_candidate_from_gap(
        gap["id"],
        title="Candidate E",
        draft_answer="Draft answer E",
    )
    candidate_id = result["candidate"]["id"]
    service.update_learning_candidate_status(candidate_id, status="approved")

    drafted = service.generate_learning_candidate_draft(candidate_id)
    imported = await service.import_learning_candidate(candidate_id, folder_id=9)

    assert drafted["status"] == "drafted"
    assert "draft_path" in drafted
    assert "Draft answer E" in (tmp_path / "drafts" / f"{candidate_id}.md").read_text(encoding="utf-8")
    assert imported["candidate"]["status"] == "imported"
    assert imported["candidate"]["document_id"] == 123
    assert imported["document"]["folder_id"] == 9
    assert imported["document"]["extra_metadata"]["candidate_id"] == candidate_id


@pytest.mark.anyio
async def test_learning_candidate_import_requires_reviewed_status(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    candidate_service = SkillKnowLearningCandidateService(
        path=tmp_path / "candidates.json",
        draft_dir=tmp_path / "drafts",
    )
    document_service = FakeDocumentService()
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        candidate_service=candidate_service,
        document_service=document_service,
    )
    gap = gap_service.upsert_from_eval_miss(question="Question F", report_id="report-1")
    result = service.create_learning_candidate_from_gap(
        gap["id"],
        title="Candidate F",
        draft_answer="Draft answer F",
    )

    with pytest.raises(LearningCandidateImportError) as exc:
        await service.import_learning_candidate(result["candidate"]["id"], folder_id=9)

    assert exc.value.code == 409
    assert "未审核" in exc.value.message
    assert document_service.created_documents == []


@pytest.mark.anyio
async def test_learning_candidate_import_is_idempotent_under_concurrency(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    candidate_service = SkillKnowLearningCandidateService(
        path=tmp_path / "candidates.json",
        draft_dir=tmp_path / "drafts",
    )
    document_service = FakeDocumentService()
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        candidate_service=candidate_service,
        document_service=document_service,
    )
    gap = gap_service.upsert_from_eval_miss(question="Question G", report_id="report-1")
    result = service.create_learning_candidate_from_gap(
        gap["id"],
        title="Candidate G",
        draft_answer="Draft answer G",
    )
    candidate_id = result["candidate"]["id"]
    service.update_learning_candidate_status(candidate_id, status="approved")
    service.generate_learning_candidate_draft(candidate_id)

    results = []

    async def run_import():
        try:
            results.append(await service.import_learning_candidate(candidate_id, folder_id=9))
        except Exception as exc:
            results.append(exc)

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(run_import)
        task_group.start_soon(run_import)

    successes = [item for item in results if isinstance(item, dict)]
    conflicts = [item for item in results if isinstance(item, LearningCandidateImportError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].code == 409
    assert len(document_service.created_documents) == 1


@pytest.mark.anyio
async def test_learning_candidate_import_failure_restores_previous_status(tmp_path):
    gap_service = SkillKnowKnowledgeGapService(path=tmp_path / "gaps.json")
    candidate_service = SkillKnowLearningCandidateService(
        path=tmp_path / "candidates.json",
        draft_dir=tmp_path / "drafts",
    )
    service = SkillKnowEvolutionService(
        report_dir=tmp_path / "reports",
        eval_service=FakeEvalService(),
        gap_service=gap_service,
        candidate_service=candidate_service,
        document_service=FailingDocumentService(),
    )
    gap = gap_service.upsert_from_eval_miss(question="Question H", report_id="report-1")
    result = service.create_learning_candidate_from_gap(
        gap["id"],
        title="Candidate H",
        draft_answer="Draft answer H",
    )
    candidate_id = result["candidate"]["id"]
    service.update_learning_candidate_status(candidate_id, status="approved")
    service.generate_learning_candidate_draft(candidate_id)

    with pytest.raises(RuntimeError):
        await service.import_learning_candidate(candidate_id, folder_id=9)

    assert candidate_service.get_candidate(candidate_id)["status"] == "drafted"
