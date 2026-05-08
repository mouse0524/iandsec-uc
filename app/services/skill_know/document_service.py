from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile
from tortoise.expressions import Q

from app.log import logger
from app.models.admin import SkillKnowDocument, SkillKnowDocumentChunk
from app.models.enums import SkillKnowDocumentStatus
from app.services.skill_know.content_analyzer import skill_know_content_analyzer
from app.services.skill_know.document_index_service import skill_know_document_index_service
from app.services.skill_know.document_parser import SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS, SUPPORTED_MARKDOWN_UPLOAD_MESSAGE, skill_know_document_parser
from app.services.skill_know.utils import document_to_dict, make_uri, new_uuid, preview_text, sha256_text
from app.settings import settings


class SkillKnowDocumentService:
    CHUNK_EXPIRE_HOURS = 24

    def _upload_dir(self) -> str:
        path = os.path.join(settings.UPLOAD_DIR, "skill_know", datetime.now().strftime("%Y%m%d"))
        os.makedirs(path, exist_ok=True)
        return path

    def _temp_dir(self) -> str:
        path = os.path.join(tempfile.gettempdir(), "skill_know_uploads")
        os.makedirs(path, exist_ok=True)
        return path

    def _chunk_dir(self) -> str:
        path = os.path.join(self._temp_dir(), "chunks")
        os.makedirs(path, exist_ok=True)
        return path

    def _cleanup_stale_chunk_dirs(self) -> None:
        root = Path(self._chunk_dir())
        if not root.exists():
            return
        expire_before = datetime.now() - timedelta(hours=self.CHUNK_EXPIRE_HOURS)
        for child in root.iterdir():
            if not child.is_dir():
                continue
            try:
                modified_at = datetime.fromtimestamp(child.stat().st_mtime)
            except OSError:
                continue
            if modified_at >= expire_before:
                continue
            for part in child.glob("*.part"):
                try:
                    part.unlink()
                except OSError:
                    pass
            try:
                child.rmdir()
            except OSError:
                pass

    async def _save_upload_to_temp(self, file: UploadFile, temp_path: str) -> int:
        size = 0
        chunk_size = 1024 * 1024
        with open(temp_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=400, detail="文件大小超限")
                f.write(chunk)
        return size

    def _metadata(self, document: SkillKnowDocument) -> dict:
        return dict(document.extra_metadata or {})

    async def _set_progress(self, document: SkillKnowDocument, stage: str, progress: int, **extra) -> None:
        metadata = self._metadata(document)
        metadata.update({"process_stage": stage, "process_progress": progress, **extra})
        document.extra_metadata = metadata
        await document.save()

    async def upload(self, file: UploadFile, *, background_tasks: BackgroundTasks, title: str | None = None, folder_id: int | None = None) -> dict:
        filename = (file.filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        ext = Path(filename).suffix.lower().lstrip(".") or "txt"
        if ext not in SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail=SUPPORTED_MARKDOWN_UPLOAD_MESSAGE)
        uid = uuid.uuid4().hex
        stored_name = f"{uid}.md"
        abs_path = os.path.join(self._upload_dir(), stored_name)
        temp_path = os.path.join(self._temp_dir(), f"{uid}.{ext}")
        temp_size = await self._save_upload_to_temp(file, temp_path)
        doc_title = title or filename
        document = await SkillKnowDocument.create(
            uuid=new_uuid(),
            uri=make_uri("documents", uid),
            title=doc_title,
            filename=filename,
            file_path=abs_path,
            file_size=0,
            file_type="md",
            folder_id=folder_id,
            extra_metadata={
                "original_filename": filename,
                "original_file_type": ext,
                "original_file_size": temp_size,
                "converted_by": "markitdown",
                "index_status": "pending",
                "process_stage": "uploaded",
                "process_progress": 5,
            },
            status=SkillKnowDocumentStatus.PROCESSING,
        )
        asyncio.create_task(self.process_document(document.id, temp_path, ext, doc_title, abs_path))
        return await document_to_dict(document)

    async def init_chunk_upload(self, data) -> dict:
        self._cleanup_stale_chunk_dirs()
        filename = data.filename.strip()
        if not filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        ext = Path(filename).suffix.lower().lstrip(".") or "txt"
        if ext not in SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail=SUPPORTED_MARKDOWN_UPLOAD_MESSAGE)
        if data.file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="文件大小超限")

        upload_id = uuid.uuid4().hex
        chunk_path = os.path.join(self._chunk_dir(), upload_id)
        os.makedirs(chunk_path, exist_ok=True)
        return {
            "upload_id": upload_id,
            "filename": filename,
            "title": data.title or filename,
            "folder_id": data.folder_id,
            "file_size": data.file_size,
            "file_type": ext,
            "total_chunks": data.total_chunks,
        }

    async def chunk_upload_status(self, upload_id: str, total_chunks: int | None = None) -> dict:
        chunk_dir = Path(self._chunk_dir()) / upload_id
        if not chunk_dir.exists() or not chunk_dir.is_dir():
            raise HTTPException(status_code=404, detail="上传任务不存在")
        uploaded_indexes = sorted(
            int(part.stem)
            for part in chunk_dir.glob("*.part")
            if part.stem.isdigit()
        )
        total = total_chunks or len(uploaded_indexes)
        progress = 0 if total <= 0 else min(100, round(len(uploaded_indexes) / total * 100))
        return {
            "upload_id": upload_id,
            "uploaded_chunks": uploaded_indexes,
            "uploaded_count": len(uploaded_indexes),
            "total_chunks": total,
            "progress": progress,
        }

    async def save_chunk(self, upload_id: str, chunk_index: int, total_chunks: int, file: UploadFile) -> dict:
        if chunk_index < 0:
            raise HTTPException(status_code=400, detail="chunk_index 非法")
        if total_chunks < 1:
            raise HTTPException(status_code=400, detail="total_chunks 非法")
        chunk_dir = os.path.join(self._chunk_dir(), upload_id)
        if not os.path.isdir(chunk_dir):
            raise HTTPException(status_code=404, detail="上传任务不存在")
        chunk_path = os.path.join(chunk_dir, f"{chunk_index:08d}.part")
        size = await self._save_upload_to_temp(file, chunk_path)
        return {"upload_id": upload_id, "chunk_index": chunk_index, "size": size, "uploaded": True}

    async def complete_chunk_upload(self, data) -> dict:
        filename = data.filename.strip()
        ext = Path(filename).suffix.lower().lstrip(".") or "txt"
        chunk_dir = os.path.join(self._chunk_dir(), data.upload_id)
        if not os.path.isdir(chunk_dir):
            raise HTTPException(status_code=404, detail="上传任务不存在")

        parts = sorted(Path(chunk_dir).glob("*.part"))
        if len(parts) != data.total_chunks:
            raise HTTPException(status_code=400, detail="分片数量不完整")

        uid = uuid.uuid4().hex
        stored_name = f"{uid}.md"
        abs_path = os.path.join(self._upload_dir(), stored_name)
        temp_path = os.path.join(self._temp_dir(), f"{uid}.{ext}")

        try:
            with open(temp_path, "wb") as merged:
                for part in parts:
                    with open(part, "rb") as src:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            merged.write(chunk)
        finally:
            for part in parts:
                try:
                    part.unlink()
                except OSError:
                    pass
            try:
                Path(chunk_dir).rmdir()
            except OSError:
                pass

        document = await SkillKnowDocument.create(
            uuid=new_uuid(),
            uri=make_uri("documents", uid),
            title=data.title or filename,
            filename=filename,
            file_path=abs_path,
            file_size=0,
            file_type="md",
            folder_id=data.folder_id,
            extra_metadata={
                "original_filename": filename,
                "original_file_type": ext,
                "original_file_size": data.file_size,
                "converted_by": "markitdown",
                "index_status": "pending",
                "process_stage": "uploaded",
                "process_progress": 5,
                "upload_mode": "chunked",
                "total_chunks": data.total_chunks,
            },
            status=SkillKnowDocumentStatus.PROCESSING,
        )
        asyncio.create_task(self.process_document(document.id, temp_path, ext, data.title or filename, abs_path))
        return await document_to_dict(document)

    async def process_document(self, document_id: int, temp_path: str, ext: str, doc_title: str, abs_path: str) -> None:
        document = await SkillKnowDocument.filter(id=document_id).first()
        if not document:
            return
        try:
            await self._set_progress(document, "converting", 20)
            content = await skill_know_document_parser.convert_to_markdown(temp_path, ext)
            content_data = content.encode("utf-8", errors="ignore")
            with open(abs_path, "wb") as f:
                f.write(content_data)

            await self._set_progress(document, "analyzing", 45)
            analysis = await skill_know_content_analyzer.analyze(doc_title, content)
            document.content = content
            document.content_hash = sha256_text(content)
            document.file_size = len(content_data)
            document.abstract = analysis["abstract"]
            document.overview = analysis["overview"]
            document.category = analysis["category"]
            document.tags = analysis["tags"]
            document.status = SkillKnowDocumentStatus.PROCESSING
            await document.save()

            await self._set_progress(document, "indexing", 70)
            try:
                index_result = await skill_know_document_index_service.rebuild(document)
            except Exception as index_exc:
                logger.exception(
                    "[skill_know.document.process.index_failed] document_id={} filename={} title={} ext={} chat_base_url={} embedding_base_url={} error={}",
                    document.id,
                    document.filename,
                    document.title,
                    ext,
                    await skill_know_config_service.get("llm_chat_base_url", await skill_know_config_service.get("llm_base_url")),
                    await skill_know_config_service.get("llm_embedding_base_url", await skill_know_config_service.get("llm_base_url")),
                    str(index_exc),
                )
                compact_error = preview_text(str(index_exc), 240)
                raise RuntimeError(f"Markdown 已生成，但索引失败: {compact_error}") from index_exc
            metadata = dict(document.extra_metadata or {})
            metadata.update(index_result)
            metadata.update({"process_stage": "completed", "process_progress": 100})
            document.extra_metadata = metadata
            document.status = SkillKnowDocumentStatus.COMPLETED
            await document.save()
        except Exception as exc:
            metadata = dict(document.extra_metadata or {})
            metadata.update({"process_stage": "failed", "process_progress": 100})
            document.extra_metadata = metadata
            document.status = SkillKnowDocumentStatus.FAILED
            document.error_message = str(exc)
            await document.save()
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    async def list(self, *, page: int, page_size: int, folder_id=None, category=None, status=None) -> tuple[int, list[dict]]:
        q = Q()
        if folder_id is not None:
            q &= Q(folder_id=folder_id)
        if category:
            q &= Q(category=category)
        if status:
            q &= Q(status=status)
        query = SkillKnowDocument.filter(q)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, [await document_to_dict(item, include_content=False) for item in rows]

    async def get(self, document_id: int) -> dict:
        document = await SkillKnowDocument.filter(id=document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        data = await document_to_dict(document)
        chunks = await SkillKnowDocumentChunk.filter(document_id=document_id).order_by("chunk_index")
        data["chunks"] = [await chunk.to_dict() for chunk in chunks]
        return data

    async def update(self, data) -> dict:
        document = await SkillKnowDocument.filter(id=data.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        for field in ["title", "description", "abstract", "overview", "content", "category", "tags", "folder_id"]:
            if field in data.model_fields_set:
                setattr(document, field, getattr(data, field))
        if "content" in data.model_fields_set:
            content_text = document.content or ""
            document.content_hash = sha256_text(content_text) if content_text else None
            document.file_size = len(content_text.encode("utf-8", errors="ignore")) if content_text else 0
            metadata = dict(document.extra_metadata or {})
            metadata["index_status"] = "pending"
            metadata["process_stage"] = "edited"
            metadata["process_progress"] = 0
            document.extra_metadata = metadata
        await document.save()
        return await document_to_dict(document)

    async def delete(self, document_id: int) -> None:
        document = await SkillKnowDocument.filter(id=document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        await skill_know_document_index_service.delete(document)
        if document.file_path:
            try:
                path = Path(document.file_path)
                upload_root = Path(settings.UPLOAD_DIR).resolve()
                if path.exists() and upload_root in path.resolve().parents:
                    path.unlink()
            except OSError:
                pass
        await document.delete()

    async def move(self, target_id: int, folder_id: int | None) -> dict:
        document = await SkillKnowDocument.filter(id=target_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        document.folder_id = folder_id
        await document.save()
        return await document_to_dict(document)

    async def search(self, query: str, *, limit: int = 20) -> list[dict]:
        rows = await SkillKnowDocument.filter(Q(title__contains=query) | Q(description__contains=query) | Q(content__contains=query)).limit(limit)
        return [await document_to_dict(item) for item in rows]

    async def reindex(self, document_id: int) -> dict:
        document = await SkillKnowDocument.filter(id=document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        if not document.content:
            raise HTTPException(status_code=400, detail="文档内容为空，无法重建索引")
        index_result = await skill_know_document_index_service.rebuild(document)
        metadata = dict(document.extra_metadata or {})
        metadata.update(index_result)
        document.extra_metadata = metadata
        await document.save()
        return await document_to_dict(document)


skill_know_document_service = SkillKnowDocumentService()
