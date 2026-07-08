import asyncio
import shutil
import uuid
from functools import partial
from pathlib import Path

import anyio
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User, WikiConversation, WikiLearningCandidate, WikiMessage, WikiPage, WikiSource
from app.schemas.base import Success, SuccessExtra
from app.schemas.wiki import (
    WikiAskIn,
    WikiDictionaryIn,
    WikiFeedbackIn,
    WikiLearningReviewIn,
    WikiPageSaveIn,
    WikiRejectIn,
    WikiUploadCompleteIn,
    WikiUploadInitIn,
)
from app.services.llm import LLMOpenAIClient, llm_openai_client
from app.services.wiki import wiki_import_service, wiki_learning_service, wiki_search_service
from app.services.wiki.wiki_builder import content_hash, normalize_page_path, slugify, wiki_builder
from app.settings import settings

router = APIRouter()
WIKI_STORAGE_ROOT = Path(settings.UPLOAD_DIR) / "wiki"
WIKI_UPLOADING_ROOT = WIKI_STORAGE_ROOT / "uploading"


def _safe_child(root: Path, rel_path: str) -> Path:
    root = root.resolve()
    path = (root / rel_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid wiki path")
    return path


def _file_item(root: Path, path: Path) -> dict:
    rel_path = path.relative_to(root).as_posix()
    return {
        "name": path.name,
        "path": rel_path,
        "type": "directory" if path.is_dir() else "file",
        "children": [_file_item(root, child) for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))] if path.is_dir() else [],
    }


def _read_text_file(root: Path, rel_path: str) -> dict:
    path = _safe_child(root, rel_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Wiki file not found")
    return {"path": rel_path, "content": path.read_text(encoding="utf-8", errors="replace")}


def _merge_upload_chunks(upload_dir: Path, filename: str, total_chunks: int) -> Path:
    merged = _safe_child(upload_dir, f"merged{Path(filename).suffix.lower()}")
    with merged.open("wb") as output:
        for index in range(total_chunks):
            with (upload_dir / f"{index}.part").open("rb") as part:
                shutil.copyfileobj(part, output)
    return merged


def _source_markdown_file(source: WikiSource) -> dict:
    if not source.markdown_path:
        raise HTTPException(status_code=404, detail="Markdown file not generated")
    path = Path(settings.BASE_DIR) / source.markdown_path
    root = (WIKI_STORAGE_ROOT / "markdown").resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Markdown file not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Markdown file not found")
    return {"path": path.relative_to(root).as_posix(), "content": path.read_text(encoding="utf-8", errors="replace")}


def _sse(data: dict) -> str:
    import json

    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _current_user() -> User:
    user = await User.filter(id=CTX_USER_ID.get()).first()
    if not user:
        raise HTTPException(status_code=401, detail="Current user not found")
    return user


async def _role_names(user: User) -> list[str]:
    return [role.name for role in await user.roles]


async def _require_wiki_editor() -> User:
    return await _require_wiki_admin()


async def _require_wiki_admin() -> User:
    user = await _current_user()
    if user.is_superuser:
        return user
    if "管理员" in set(await _role_names(user)):
        return user
    raise HTTPException(status_code=403, detail="Only admin can manage wiki records")


def _message_preview(content: str, limit: int = 80) -> str:
    text = " ".join(str(content or "").split())
    return text[:limit].rstrip()


def _status(stage: str, label: str) -> str:
    return _sse({"type": "status", "payload": {"stage": stage, "label": label}})


async def _wiki_conversation(conversation_id: int | None, *, question: str, owner_id: int) -> WikiConversation:
    if conversation_id:
        conversation = await WikiConversation.filter(id=conversation_id, owner_id=owner_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        return conversation
    return await WikiConversation.create(title=_message_preview(question, 60) or "新对话", owner_id=owner_id)


async def _conversation_row(row: WikiConversation) -> dict:
    data = await row.to_dict()
    last = await WikiMessage.filter(conversation_id=row.id, owner_id=row.owner_id).order_by("-id").first()
    data["last_message_preview"] = _message_preview(last.content if last else "")
    data["last_message_role"] = last.role if last else ""
    return data


async def _qa_record_row(message: WikiMessage) -> dict:
    data = await message.to_dict()
    question = await WikiMessage.filter(
        conversation_id=message.conversation_id,
        owner_id=message.owner_id,
        role="user",
        id__lt=message.id,
    ).order_by("-id").first()
    owner = await User.filter(id=message.owner_id).first()
    data["question"] = question.content if question else ""
    data["owner_name"] = owner.alias or owner.username if owner else ""
    return data


async def _save_wiki_turn(
    *,
    conversation: WikiConversation,
    question: str,
    answer: str,
    citations: list[dict],
    archive_path: str | None = None,
) -> WikiMessage:
    await WikiMessage.create(
        conversation_id=conversation.id,
        owner_id=conversation.owner_id,
        role="user",
        content=question,
    )
    return await WikiMessage.create(
        conversation_id=conversation.id,
        owner_id=conversation.owner_id,
        role="assistant",
        content=answer,
        citations=citations,
        archive_path=archive_path,
    )


async def _message_question(message: WikiMessage) -> str:
    question = await WikiMessage.filter(
        conversation_id=message.conversation_id,
        owner_id=message.owner_id,
        role="user",
        id__lt=message.id,
    ).order_by("-id").first()
    return question.content if question else ""


@router.post("/source/upload", summary="Upload wiki source", dependencies=[DependAuth])
async def upload_source(file: UploadFile = File(...)):
    user = await _require_wiki_editor()
    source, created = await wiki_import_service.create_source(user_id=user.id, file=file)
    if created and source.status != "completed":
        asyncio.create_task(wiki_import_service.process(source.id))
    return Success(data=await source.to_dict())


@router.post("/source/upload/init", summary="Init chunked wiki source upload", dependencies=[DependAuth])
async def init_source_upload(payload: WikiUploadInitIn):
    await _require_wiki_editor()
    filename = Path(payload.filename).name
    ext = Path(filename).suffix.lower()
    from app.services.wiki.markdown_converter import SUPPORTED_WIKI_EXTENSIONS

    if ext not in SUPPORTED_WIKI_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    upload_id = uuid.uuid4().hex
    target = _safe_child(WIKI_UPLOADING_ROOT, upload_id)
    target.mkdir(parents=True, exist_ok=True)
    return Success(data={"upload_id": upload_id, "chunk_size": 2 * 1024 * 1024})


@router.post("/source/upload/chunk", summary="Upload wiki source chunk", dependencies=[DependAuth])
async def upload_source_chunk(upload_id: str = Query(...), chunk_index: int = Query(..., ge=0), chunk: UploadFile = File(...)):
    await _require_wiki_editor()
    target_dir = _safe_child(WIKI_UPLOADING_ROOT, upload_id)
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Upload session not found")
    target = _safe_child(target_dir, f"{chunk_index}.part")
    with target.open("wb") as output:
        while data := await chunk.read(1024 * 1024):
            output.write(data)
    return Success(data={"chunk_index": chunk_index})


@router.post("/source/upload/complete", summary="Complete chunked wiki source upload", dependencies=[DependAuth])
async def complete_source_upload(payload: WikiUploadCompleteIn):
    user = await _require_wiki_editor()
    upload_dir = _safe_child(WIKI_UPLOADING_ROOT, payload.upload_id)
    if not upload_dir.is_dir():
        raise HTTPException(status_code=404, detail="Upload session not found")
    missing = [index for index in range(payload.total_chunks) if not (upload_dir / f"{index}.part").is_file()]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing chunks: {missing[:5]}")
    merged = await anyio.to_thread.run_sync(_merge_upload_chunks, upload_dir, payload.filename, payload.total_chunks)
    source, created = await wiki_import_service.create_source_from_path(user_id=user.id, filename=payload.filename, raw_path=merged)
    await anyio.to_thread.run_sync(partial(shutil.rmtree, upload_dir, ignore_errors=True))
    if created and source.status != "completed":
        asyncio.create_task(wiki_import_service.process(source.id))
    return Success(data=await source.to_dict())


@router.post("/source/retry", summary="Retry wiki import", dependencies=[DependAuth])
async def retry_source(source_id: int = Query(...)):
    await _require_wiki_editor()
    source = await WikiSource.get(id=source_id)
    source.status = "pending"
    source.error_message = None
    await source.save()
    asyncio.create_task(wiki_import_service.process(source.id))
    return Success(data=await source.to_dict())


@router.delete("/source/delete", summary="Delete wiki source", dependencies=[DependAuth])
async def delete_source(source_id: int = Query(...)):
    await _require_wiki_editor()
    await wiki_import_service.delete_source(source_id)
    return Success(msg="Deleted")


@router.get("/source/list", summary="List wiki sources", dependencies=[DependAuth])
async def list_sources(page: int = 1, page_size: int = 10, keyword: str | None = None):
    query = WikiSource.all()
    if keyword:
        query = query.filter(title__icontains=keyword)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await row.to_dict() for row in rows], total=total, page=page, page_size=page_size)


@router.get("/source/markdown", summary="Get source markdown", dependencies=[DependAuth])
async def get_source_markdown(source_id: int = Query(...)):
    source = await WikiSource.get(id=source_id)
    return Success(data=_source_markdown_file(source))


@router.get("/conversations", summary="List wiki conversations", dependencies=[DependAuth])
async def list_conversations(page: int = 1, page_size: int = 50):
    user = await _current_user()
    query = WikiConversation.filter(owner_id=user.id)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await _conversation_row(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/conversations/get", summary="Get wiki conversation", dependencies=[DependAuth])
async def get_conversation(conversation_id: int = Query(...)):
    user = await _current_user()
    conversation = await WikiConversation.filter(id=conversation_id, owner_id=user.id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    data = await conversation.to_dict()
    messages = await WikiMessage.filter(conversation_id=conversation.id, owner_id=user.id).order_by("id")
    data["messages"] = [await item.to_dict() for item in messages]
    return Success(data=data)


@router.get("/file/tree", summary="List llm-wiki files", dependencies=[DependAuth])
async def file_tree():
    wiki_builder._ensure_layout()
    roots = {
        "raw": WIKI_STORAGE_ROOT / "raw",
        "wiki": WIKI_STORAGE_ROOT / "wiki",
        "schema": WIKI_STORAGE_ROOT,
    }
    data = []
    for layer, root in roots.items():
        if layer == "schema":
            children = [
                _file_item(root, item)
                for item in sorted(root.glob("*.md"), key=lambda path: path.name.lower())
            ]
            data.append({"name": "schema", "path": "", "type": "directory", "layer": layer, "children": children})
            continue
        root.mkdir(parents=True, exist_ok=True)
        item = _file_item(root, root)
        item["name"] = layer
        item["layer"] = layer
        data.append(item)
    return Success(data=data)


@router.get("/file/get", summary="Get llm-wiki file", dependencies=[DependAuth])
async def get_file(layer: str = Query(...), path: str = Query(...)):
    if layer == "raw":
        return Success(data=_read_text_file(WIKI_STORAGE_ROOT / "raw", path))
    if layer == "wiki":
        return Success(data=_read_text_file(WIKI_STORAGE_ROOT / "wiki", path))
    if layer == "schema":
        return Success(data=_read_text_file(WIKI_STORAGE_ROOT, path))
    raise HTTPException(status_code=400, detail="Invalid wiki layer")


@router.get("/asset", summary="Get wiki asset", dependencies=[DependAuth])
async def get_asset(path: str = Query(...)):
    target = _safe_child(WIKI_STORAGE_ROOT / "wiki", path)
    if not target.is_file() or not target.relative_to(WIKI_STORAGE_ROOT / "wiki").as_posix().startswith("assets/"):
        raise HTTPException(status_code=404, detail="Wiki asset not found")
    return FileResponse(target)


@router.get("/health", summary="Check llm-wiki health", dependencies=[DependAuth])
async def health():
    wiki_builder._ensure_layout()
    source_count = await WikiSource.all().count()
    if source_count == 0:
        await wiki_import_service.cleanup_generated_wiki()
    repaired_page_files = await wiki_builder.repair_page_files()
    required = [
        WIKI_STORAGE_ROOT / "raw",
        WIKI_STORAGE_ROOT / "wiki",
        WIKI_STORAGE_ROOT / "wiki" / "index.md",
        WIKI_STORAGE_ROOT / "wiki" / "overview.md",
        WIKI_STORAGE_ROOT / "wiki" / "log.md",
        WIKI_STORAGE_ROOT / "wiki" / "glossary.md",
        WIKI_STORAGE_ROOT / "wiki" / "queries",
        WIKI_STORAGE_ROOT / "AGENTS.md",
    ]
    missing = [path.relative_to(WIKI_STORAGE_ROOT).as_posix() for path in required if not path.exists()]
    pages = await WikiPage.all()
    missing_page_files = [
        page.path for page in pages if page.path and not (WIKI_STORAGE_ROOT / "wiki" / page.path).exists()
    ]
    return Success(
        data={
            "ok": not missing and not missing_page_files,
            "missing": missing,
            "missing_page_files": missing_page_files,
            "repaired_page_files": repaired_page_files,
            "page_count": len(pages),
            "source_count": source_count,
        }
    )


@router.get("/page/list", summary="List wiki pages", dependencies=[DependAuth])
async def list_pages(page: int = 1, page_size: int = 10, keyword: str | None = None, page_type: str | None = None):
    query = WikiPage.all()
    if keyword:
        query = query.filter(title__icontains=keyword)
    if page_type:
        query = query.filter(page_type=page_type)
    total = await query.count()
    rows = await query.order_by("path").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await row.to_dict() for row in rows], total=total, page=page, page_size=page_size)


@router.get("/page/get", summary="Get wiki page", dependencies=[DependAuth])
async def get_page(page_id: int = Query(...)):
    page = await WikiPage.get(id=page_id)
    return Success(data=await page.to_dict())


@router.post("/page/save", summary="Save wiki page", dependencies=[DependAuth])
async def save_page(payload: WikiPageSaveIn):
    await _require_wiki_editor()
    body = payload.content.strip()
    page_hash = content_hash(body)
    path = normalize_page_path(payload.path or f"{payload.page_type}s/{slugify(payload.title)}")
    if payload.page_id:
        page = await WikiPage.get(id=payload.page_id)
        page.path = path
        page.title = payload.title.strip()
        page.page_type = payload.page_type
        page.summary = payload.summary
        page.content = body
        page.content_hash = page_hash
        await page.save()
    else:
        page, _ = await WikiPage.get_or_create(
            path=path,
            defaults={
                "title": payload.title.strip(),
                "page_type": payload.page_type,
                "summary": payload.summary,
                "content": body,
                "content_hash": page_hash,
            },
        )
        if page.content_hash != page_hash:
            page.title = payload.title.strip()
            page.page_type = payload.page_type
            page.summary = payload.summary
            page.content = body
            page.content_hash = page_hash
            await page.save()
    wiki_builder._write_page(path, body)
    return Success(data=await page.to_dict())


@router.get("/search", summary="Search wiki pages", dependencies=[DependAuth])
async def search_pages(keyword: str = Query(..., min_length=1), limit: int = 10):
    return Success(data=await wiki_search_service.search(keyword, limit=limit))


@router.get("/dictionary", summary="Get wiki dictionary", dependencies=[DependAuth])
async def get_dictionary():
    await _require_wiki_editor()
    return Success(data=await wiki_search_service.dictionary())


@router.post("/dictionary", summary="Save wiki dictionary", dependencies=[DependAuth])
async def save_dictionary(payload: WikiDictionaryIn):
    await _require_wiki_editor()
    data = await wiki_search_service.save_dictionary(
        domain_terms=payload.domain_terms,
        stop_words=payload.stop_words,
    )
    return Success(data=data)


@router.post("/ask", summary="Ask wiki", dependencies=[DependAuth])
async def ask_wiki(payload: WikiAskIn):
    matches = await wiki_search_service.search(payload.question, limit=5)
    if not matches:
        candidate = await wiki_learning_service.create_candidate(
            question=payload.question,
            answer=None,
            evidence_page_ids=[],
            reason="no_match",
        )
        answer = "Wiki 中还没有匹配的知识，已生成待学习记录。"
        return Success(data={"answer": answer, "citations": [], "candidate_id": candidate.id, "archive_path": None})
    context = "\n\n".join(f"[{item['id']}] {item['title']}\n{item['content'][:4000]}" for item in matches)
    result = await llm_openai_client.chat(
        [
            {"role": "system", "content": "只基于给定的企业 Wiki 上下文用中文回答，并引用页面 ID。"},
            {"role": "user", "content": f"Question: {payload.question}\n\nContext:\n{context}"},
        ]
    )
    answer = LLMOpenAIClient._message_content(result).strip()
    if not answer:
        candidate = await wiki_learning_service.create_candidate(
            question=payload.question,
            answer=None,
            evidence_page_ids=[item["id"] for item in matches],
            reason="empty_answer",
        )
        answer = "模型没有生成有效回答，已生成待学习记录。"
        return Success(data={"answer": answer, "citations": matches, "candidate_id": candidate.id, "archive_path": None})
    return Success(data={"answer": answer, "citations": matches, "candidate_id": None, "archive_path": None})


@router.post("/ask/stream", summary="Ask wiki stream", dependencies=[DependAuth])
async def ask_wiki_stream(payload: WikiAskIn):
    user = await _current_user()
    conversation = await _wiki_conversation(payload.conversation_id, question=payload.question, owner_id=user.id)

    async def generate():
        try:
            yield _status("search", "正在查询 Wiki")
            matches = await wiki_search_service.search(payload.question, limit=5)
            if not matches:
                yield _status("learn", "未命中，正在生成待学习记录")
                candidate = await wiki_learning_service.create_candidate(
                    question=payload.question,
                    answer=None,
                    evidence_page_ids=[],
                    reason="no_match",
                )
                answer = "Wiki 中还没有匹配的知识，已生成待学习记录。"
                message = await _save_wiki_turn(
                    conversation=conversation,
                    question=payload.question,
                    answer=answer,
                    citations=[],
                )
                yield _sse({"type": "final", "payload": {"conversation_id": conversation.id, "message_id": message.id, "content": answer, "citations": [], "candidate_id": candidate.id, "archive_path": None}})
                return

            yield _status("llm", f"已命中 {len(matches)} 个 Wiki 页面，正在调用大模型")
            context = "\n\n".join(f"[{item['id']}] {item['title']}\n{item['content'][:4000]}" for item in matches)
            messages = [
                {"role": "system", "content": "只基于给定的企业 Wiki 上下文用中文回答，并引用页面 ID。"},
                {"role": "user", "content": f"Question: {payload.question}\n\nContext:\n{context}"},
            ]
            answer = ""
            async for chunk in llm_openai_client.stream_chat(messages):
                choices = chunk.get("choices") if isinstance(chunk, dict) else None
                delta = ((choices or [{}])[0].get("delta") or {}).get("content") if choices else ""
                if not delta:
                    continue
                answer += delta
                yield _sse({"type": "assistant.delta", "payload": {"content": delta}})
            if not answer.strip():
                yield _status("learn", "模型未返回有效内容，正在生成待学习记录")
                candidate = await wiki_learning_service.create_candidate(
                    question=payload.question,
                    answer=None,
                    evidence_page_ids=[item["id"] for item in matches],
                    reason="empty_answer",
                )
                answer = "模型没有生成有效回答，已生成待学习记录。"
                message = await _save_wiki_turn(
                    conversation=conversation,
                    question=payload.question,
                    answer=answer,
                    citations=matches,
                )
                yield _sse({"type": "final", "payload": {"conversation_id": conversation.id, "message_id": message.id, "content": answer, "citations": matches, "candidate_id": candidate.id, "archive_path": None}})
                return
            yield _status("save", "正在保存问答记录")
            message = await _save_wiki_turn(
                conversation=conversation,
                question=payload.question,
                answer=answer,
                citations=matches,
            )
            yield _sse({"type": "final", "payload": {"conversation_id": conversation.id, "message_id": message.id, "content": answer, "citations": matches, "candidate_id": None, "archive_path": None}})
        except Exception as exc:
            yield _sse({"type": "error", "payload": {"message": str(exc) or "Wiki 问答失败"}})

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/feedback/unhelpful", summary="Mark wiki answer unhelpful", dependencies=[DependAuth])
async def mark_unhelpful(payload: WikiFeedbackIn):
    candidate = await wiki_learning_service.create_candidate(
        question=payload.question,
        answer=payload.answer,
        evidence_page_ids=payload.evidence_page_ids,
        reason="unhelpful_feedback",
    )
    return Success(data=await candidate.to_dict())


@router.get("/learning/list", summary="List wiki learning candidates", dependencies=[DependAuth])
async def list_learning(page: int = 1, page_size: int = 10, status: str | None = "pending"):
    await _require_wiki_admin()
    query = WikiLearningCandidate.all()
    if status:
        query = query.filter(status=status)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await row.to_dict() for row in rows], total=total, page=page, page_size=page_size)


@router.post("/learning/approve", summary="Approve wiki learning candidate", dependencies=[DependAuth])
async def approve_learning(payload: WikiLearningReviewIn):
    user = await _require_wiki_admin()
    candidate = await wiki_learning_service.approve(
        candidate_id=payload.candidate_id,
        reviewer_id=user.id,
        content=payload.content,
    )
    return Success(data=await candidate.to_dict())


@router.post("/learning/reject", summary="Reject wiki learning candidate", dependencies=[DependAuth])
async def reject_learning(payload: WikiRejectIn):
    user = await _require_wiki_admin()
    candidate = await wiki_learning_service.reject(candidate_id=payload.candidate_id, reviewer_id=user.id)
    return Success(data=await candidate.to_dict())


@router.get("/admin/messages", summary="List wiki Q&A records", dependencies=[DependAuth])
async def list_admin_messages(page: int = 1, page_size: int = 10, keyword: str | None = None):
    await _require_wiki_admin()
    query = WikiMessage.filter(role="assistant")
    if keyword:
        query = query.filter(content__icontains=keyword)
    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
    return SuccessExtra(data=[await _qa_record_row(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/admin/messages/archive", summary="Archive wiki Q&A record", dependencies=[DependAuth])
async def archive_admin_message(message_id: int = Query(...)):
    await _require_wiki_admin()
    message = await WikiMessage.get(id=message_id)
    if message.role != "assistant":
        raise HTTPException(status_code=400, detail="Only assistant messages can be archived")
    if not message.archive_path:
        message.archive_path = await wiki_builder.archive_query(
            question=await _message_question(message),
            answer=message.content,
            citations=message.citations or [],
        )
        await message.save()
    return Success(data=await _qa_record_row(message))
