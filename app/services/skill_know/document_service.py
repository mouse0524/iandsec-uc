from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile
from tortoise.expressions import Q

from app.models.admin import SkillKnowDocument
from app.models.enums import SkillKnowDocumentStatus
from app.services.skill_know.content_analyzer import skill_know_content_analyzer
from app.services.skill_know.document_index_service import skill_know_document_index_service
from app.services.skill_know.document_parser import SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS, SUPPORTED_MARKDOWN_UPLOAD_MESSAGE, skill_know_document_parser
from app.services.skill_know.utils import document_to_dict, make_uri, new_uuid, sha256_text
from app.settings import settings


class SkillKnowDocumentService:
    def _upload_dir(self) -> str:
        path = os.path.join(settings.UPLOAD_DIR, "skill_know", datetime.now().strftime("%Y%m%d"))
        os.makedirs(path, exist_ok=True)
        return path

    def _temp_dir(self) -> str:
        path = os.path.join(tempfile.gettempdir(), "skill_know_uploads")
        os.makedirs(path, exist_ok=True)
        return path

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
        content_bytes = await file.read()
        if len(content_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="文件大小超限")
        with open(temp_path, "wb") as f:
            f.write(content_bytes)
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
                "original_file_size": len(content_bytes),
                "converted_by": "markitdown",
                "index_status": "pending",
                "process_stage": "uploaded",
                "process_progress": 5,
            },
            status=SkillKnowDocumentStatus.PROCESSING,
        )
        background_tasks.add_task(self.process_document, document.id, temp_path, ext, doc_title, abs_path)
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
                raise RuntimeError(f"Markdown 已生成，但索引失败: {index_exc}") from index_exc
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
        return await document_to_dict(document)

    async def update(self, data) -> dict:
        document = await SkillKnowDocument.filter(id=data.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        for field in ["title", "description", "category", "tags", "folder_id"]:
            if field in data.model_fields_set:
                setattr(document, field, getattr(data, field))
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
