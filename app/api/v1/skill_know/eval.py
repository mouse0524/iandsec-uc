from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.schemas.base import Success
from app.schemas.skill_know import SkillKnowGoldenCaseIn
from app.services.skill_know.eval_service import SkillKnowEvalCase, skill_know_eval_service
from app.services.skill_know.golden_case_service import skill_know_golden_case_service
from app.services.skill_know.retrieval_debug_service import skill_know_retrieval_debug_service

router = APIRouter()


class SkillKnowEvalCaseIn(BaseModel):
    question: str = Field(..., min_length=1)
    expected_document_id: int | None = None
    expected_section_id: int | None = None
    expected_heading_contains: str | None = None


class SkillKnowEvalIn(BaseModel):
    cases: list[SkillKnowEvalCaseIn] = Field(default_factory=list)


@router.post("/retrieval", summary="评测知识库检索命中率")
async def evaluate_retrieval(payload: SkillKnowEvalIn, top_k: int = Query(8, ge=1, le=20)):
    cases = [
        SkillKnowEvalCase(
            question=item.question,
            expected_document_id=item.expected_document_id,
            expected_section_id=item.expected_section_id,
            expected_heading_contains=item.expected_heading_contains,
        )
        for item in payload.cases
    ]
    return Success(data=await skill_know_eval_service.evaluate_cases(cases, top_k=top_k))


@router.get("/debug", summary="调试单次知识库检索")
async def debug_retrieval(query: str = Query(..., min_length=1), top_k: int = Query(8, ge=1, le=20)):
    return Success(data=await skill_know_retrieval_debug_service.debug(query, top_k=top_k))


@router.post("/golden", summary="运行黄金问题检索评估")
async def evaluate_golden_retrieval(top_k: int = Query(8, ge=1, le=20)):
    return Success(data=await skill_know_eval_service.evaluate_golden_cases(top_k=top_k))


@router.get("/golden/cases", summary="黄金问题列表")
async def list_golden_cases():
    return Success(data=skill_know_golden_case_service.list_cases())


@router.post("/golden/cases", summary="保存黄金问题")
async def save_golden_case(payload: SkillKnowGoldenCaseIn):
    return Success(data=skill_know_golden_case_service.upsert(payload))


@router.delete("/golden/cases", summary="删除黄金问题")
async def delete_golden_case(case_id: str = Query(...)):
    skill_know_golden_case_service.delete(case_id)
    return Success(msg="删除成功")
