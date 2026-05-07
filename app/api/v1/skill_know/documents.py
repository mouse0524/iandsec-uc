from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile

from app.models.enums import SkillKnowDocumentStatus
from app.schemas.base import Success, SuccessExtra
from app.schemas.skill_know import SkillKnowChunkUploadCompleteIn, SkillKnowChunkUploadInitIn, SkillKnowDocumentUpdate, SkillKnowMoveIn
from app.services.skill_know.document_service import skill_know_document_service

router = APIRouter()


@router.post("/upload", summary="上传文档")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = None,
    folder_id: int | None = None,
):
    return Success(data=await skill_know_document_service.upload(file, background_tasks=background_tasks, title=title, folder_id=folder_id))


@router.post("/upload/init", summary="初始化分片上传")
async def init_chunk_upload(payload: SkillKnowChunkUploadInitIn):
    return Success(data=await skill_know_document_service.init_chunk_upload(payload))


@router.post("/upload/chunk", summary="上传文档分片")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file: UploadFile = File(...),
):
    return Success(data=await skill_know_document_service.save_chunk(upload_id, chunk_index, total_chunks, file))


@router.post("/upload/complete", summary="完成分片上传")
async def complete_chunk_upload(payload: SkillKnowChunkUploadCompleteIn):
    return Success(data=await skill_know_document_service.complete_chunk_upload(payload))


@router.get("/list", summary="文档列表")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    folder_id: int | None = Query(None),
    category: str | None = Query(None),
    status: SkillKnowDocumentStatus | None = Query(None),
):
    total, rows = await skill_know_document_service.list(
        page=page,
        page_size=page_size,
        folder_id=folder_id,
        category=category,
        status=status,
    )
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/get", summary="文档详情")
async def get_document(document_id: int = Query(...)):
    return Success(data=await skill_know_document_service.get(document_id))


@router.post("/update", summary="更新文档")
async def update_document(payload: SkillKnowDocumentUpdate):
    return Success(data=await skill_know_document_service.update(payload))


@router.delete("/delete", summary="删除文档")
async def delete_document(document_id: int = Query(...)):
    await skill_know_document_service.delete(document_id)
    return Success(msg="删除成功")


@router.post("/move", summary="移动文档")
async def move_document(payload: SkillKnowMoveIn):
    return Success(data=await skill_know_document_service.move(payload.target_id, payload.folder_id))


@router.get("/search", summary="搜索文档")
async def search_documents(q: str = Query(...), limit: int = Query(20, ge=1, le=100)):
    rows = await skill_know_document_service.search(q, limit=limit)
    return Success(data={"items": rows, "total": len(rows)})


@router.post("/reindex", summary="重建文档索引")
async def reindex_document(document_id: int = Query(...)):
    return Success(data=await skill_know_document_service.reindex(document_id))
