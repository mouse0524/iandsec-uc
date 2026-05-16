from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.schemas.base import Fail, Success
from app.services.skill_know.evolution_service import LearningCandidateImportError, skill_know_evolution_service

router = APIRouter()


class SkillKnowEvolutionSettingsIn(BaseModel):
    enabled: bool = True
    run_at: str = Field(default="02:10", pattern=r"^\d{1,2}:\d{2}$")
    top_k: int = Field(default=8, ge=1, le=20)


class SkillKnowGapStatusIn(BaseModel):
    status: str = Field(..., pattern="^(pending|ignored|resolved)$")


class SkillKnowGapToGoldenCaseIn(BaseModel):
    expected_document_id: int | None = None
    expected_section_id: int | None = None
    expected_heading_contains: str | None = None


class SkillKnowLearningCandidateIn(BaseModel):
    title: str | None = None
    draft_answer: str | None = None


class SkillKnowLearningCandidateStatusIn(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")
    review_note: str | None = None


class SkillKnowCandidateImportIn(BaseModel):
    folder_id: int | None = None


@router.get("/settings", summary="知识库自进化设置")
async def get_evolution_settings():
    return Success(data=await skill_know_evolution_service.get_settings())


@router.post("/settings", summary="保存知识库自进化设置")
async def save_evolution_settings(payload: SkillKnowEvolutionSettingsIn):
    return Success(data=await skill_know_evolution_service.save_settings(payload.model_dump()))


@router.post("/reports/run", summary="运行知识库自进化每日评测报告")
async def run_daily_eval_report(top_k: int = Query(8, ge=1, le=20)):
    return Success(data=await skill_know_evolution_service.run_daily_eval_report(top_k=top_k))


@router.get("/reports", summary="知识库自进化报告列表")
async def list_evolution_reports(limit: int = Query(20, ge=1, le=100)):
    return Success(data=skill_know_evolution_service.list_reports(limit=limit))


@router.get("/gaps", summary="知识库自进化缺口列表")
async def list_knowledge_gaps(status: str | None = Query(None), limit: int = Query(200, ge=1, le=500)):
    return Success(data=skill_know_evolution_service.list_knowledge_gaps(status=status, limit=limit))


@router.get("/candidates", summary="知识库自进化学习候选列表")
async def list_learning_candidates(status: str | None = Query(None), limit: int = Query(200, ge=1, le=500)):
    return Success(data=skill_know_evolution_service.list_learning_candidates(status=status, limit=limit))


@router.post("/gaps/{gap_id}/status", summary="更新知识缺口状态")
async def update_knowledge_gap_status(gap_id: str, payload: SkillKnowGapStatusIn):
    gap = skill_know_evolution_service.update_knowledge_gap_status(gap_id, status=payload.status)
    if not gap:
        return Fail(code=404, msg="知识缺口不存在")
    return Success(data=gap)


@router.post("/gaps/{gap_id}/golden-case", summary="将知识缺口转为黄金问题")
async def convert_gap_to_golden_case(gap_id: str, payload: SkillKnowGapToGoldenCaseIn):
    result = skill_know_evolution_service.convert_gap_to_golden_case(gap_id, **payload.model_dump())
    if not result:
        return Fail(code=404, msg="知识缺口不存在")
    return Success(data=result)


@router.post("/gaps/{gap_id}/candidate", summary="将知识缺口转为学习候选")
async def create_learning_candidate_from_gap(gap_id: str, payload: SkillKnowLearningCandidateIn):
    result = skill_know_evolution_service.create_learning_candidate_from_gap(gap_id, **payload.model_dump())
    if not result:
        return Fail(code=404, msg="知识缺口不存在")
    return Success(data=result)


@router.post("/candidates/{candidate_id}/status", summary="更新学习候选审核状态")
async def update_learning_candidate_status(candidate_id: str, payload: SkillKnowLearningCandidateStatusIn):
    candidate = skill_know_evolution_service.update_learning_candidate_status(candidate_id, **payload.model_dump())
    if not candidate:
        return Fail(code=404, msg="学习候选不存在")
    return Success(data=candidate)


@router.post("/candidates/{candidate_id}/draft", summary="生成学习候选 Markdown 草稿")
async def generate_learning_candidate_draft(candidate_id: str):
    candidate = skill_know_evolution_service.generate_learning_candidate_draft(candidate_id)
    if not candidate:
        return Fail(code=404, msg="学习候选不存在")
    return Success(data=candidate)


@router.post("/candidates/{candidate_id}/import", summary="将学习候选入库为知识文档")
async def import_learning_candidate(candidate_id: str, payload: SkillKnowCandidateImportIn):
    try:
        result = await skill_know_evolution_service.import_learning_candidate(candidate_id, folder_id=payload.folder_id)
    except LearningCandidateImportError as exc:
        return Fail(code=exc.code, msg=exc.message)
    if not result:
        return Fail(code=404, msg="学习候选不存在")
    return Success(data=result)


@router.get("/reports/{report_id}", summary="知识库自进化报告详情")
async def get_evolution_report(report_id: str):
    report = skill_know_evolution_service.get_report(report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    return Success(data=report)

