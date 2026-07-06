import os
import shutil
import uuid
import hashlib
import re
from functools import partial
from pathlib import Path

import anyio
from fastapi import HTTPException, UploadFile

from app.models.admin import WikiIngestJob, WikiLink, WikiPage, WikiSource
from app.services.wiki.markdown_converter import SUPPORTED_WIKI_EXTENSIONS, convert_to_markdown
from app.services.wiki.wiki_builder import wiki_builder
from app.services.llm import LLMOpenAIClient, llm_openai_client
from app.settings import settings


class WikiImportService:
    def __init__(self):
        self.root = Path(settings.UPLOAD_DIR) / "wiki"

    async def create_source(self, *, user_id: int, file: UploadFile) -> WikiSource:
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_WIKI_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        raw_dir = self.root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_name = f"{uuid.uuid4().hex}{ext}"
        raw_path = raw_dir / raw_name
        digestor = hashlib.sha256()
        size = 0
        with raw_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                digestor.update(chunk)
                size += len(chunk)
                target.write(chunk)
        return await self.create_source_from_path(user_id=user_id, filename=filename or raw_name, raw_path=raw_path)

    async def create_source_from_path(self, *, user_id: int, filename: str, raw_path: Path) -> WikiSource:
        filename = Path(filename or raw_path.name).name
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_WIKI_EXTENSIONS:
            raw_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        digest, size = await anyio.to_thread.run_sync(self._file_digest, raw_path)
        old = await WikiSource.filter(content_hash=digest, status="completed").first()
        if old:
            raw_path.unlink(missing_ok=True)
            return old
        raw_dir = self.root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        final_path = raw_dir / f"{uuid.uuid4().hex}{ext}"
        if raw_path.resolve() != final_path.resolve():
            shutil.move(str(raw_path), final_path)
        source = await WikiSource.create(
            title=Path(filename).stem or final_path.name,
            filename=filename or final_path.name,
            file_path=os.path.relpath(final_path, settings.BASE_DIR),
            file_type=ext,
            file_size=size,
            content_hash=digest,
            created_by=user_id,
        )
        await WikiIngestJob.create(source_id=source.id)
        return source

    @staticmethod
    def _file_digest(path: Path) -> tuple[str, int]:
        digestor = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digestor.update(chunk)
                size += len(chunk)
        return digestor.hexdigest(), size

    async def process(self, source_id: int) -> None:
        source = await WikiSource.get(id=source_id)
        job = await WikiIngestJob.filter(source_id=source.id).order_by("-id").first()
        try:
            if job:
                job.status = "running"
                job.stage = "convert"
                await job.save()
            raw_path = Path(settings.BASE_DIR) / source.file_path
            asset_dir = self.root / "wiki" / "assets" / source.content_hash
            markdown = await anyio.to_thread.run_sync(
                partial(
                    convert_to_markdown,
                    raw_path,
                    asset_dir=asset_dir,
                    asset_prefix=f"assets/{source.content_hash}",
                )
            )
            markdown = await self.polish_markdown(source=source, raw_path=raw_path, markdown=markdown)
            markdown_dir = self.root / "markdown"
            markdown_dir.mkdir(parents=True, exist_ok=True)
            markdown_path = markdown_dir / f"{source.content_hash}.md"
            markdown_path.write_text(markdown, encoding="utf-8")
            source.markdown_path = os.path.relpath(markdown_path, settings.BASE_DIR)
            source.status = "building"
            source.error_message = None
            await source.save()
            if job:
                job.stage = "build"
                await job.save()
            await wiki_builder.build(source, markdown)
            source.status = "completed"
            await source.save()
            if job:
                job.status = "completed"
                job.stage = "completed"
                await job.save()
        except Exception as exc:
            source.status = "failed"
            source.error_message = str(exc)
            await source.save()
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                await job.save()

    async def polish_markdown(self, *, source: WikiSource, raw_path: Path, markdown: str) -> str:
        source_excerpt = self._source_excerpt(raw_path)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是企业 LLM Wiki 的 Markdown 编译器。只允许根据原始资料校对和整理 Markdown，"
                    "不能新增事实，不能改数字、版本号、产品名、步骤顺序、图片链接。"
                    "发现缺失、歧义或无法确认时，用 blockquote 写“待确认：...”。"
                    "只返回修订后的 Markdown，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"文件名：{source.filename}\n文件类型：{source.file_type}\n\n"
                    f"原始资料摘录：\n{source_excerpt[:20000]}\n\n"
                    f"待校对 Markdown：\n{markdown[:30000]}"
                ),
            },
        ]
        try:
            result = await llm_openai_client.chat(messages, timeout=180)
            revised = self._markdown_text(LLMOpenAIClient._message_content(result))
        except Exception:
            return markdown
        return revised if self._safe_revision(markdown, revised) else markdown

    def _source_excerpt(self, path: Path) -> str:
        if path.suffix.lower() not in {".md", ".txt", ".csv", ".html", ".htm"}:
            return "二进制文档，原始资料以 Docling 转换后的 Markdown 和图片链接为准。"
        data = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")

    @staticmethod
    def _markdown_text(raw: str) -> str:
        text = str(raw or "").strip()
        fenced = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, re.S | re.I)
        return (fenced.group(1) if fenced else text).strip()

    @staticmethod
    def _safe_revision(original: str, revised: str) -> bool:
        if len(revised.strip()) < int(len(original.strip()) * 0.55):
            return False
        original_assets = set(re.findall(r"!\[[^\]]*\]\((assets/[^)]+)\)", original))
        revised_assets = set(re.findall(r"!\[[^\]]*\]\((assets/[^)]+)\)", revised))
        # ponytail: heuristic guard; add a diff-review queue if legal-grade traceability becomes required.
        return original_assets.issubset(revised_assets)

    async def delete_source(self, source_id: int) -> None:
        source = await WikiSource.get(id=source_id)
        await self._delete_pages(await WikiPage.filter(source_id=source.id))
        await WikiIngestJob.filter(source_id=source.id).delete()
        for rel_path in [source.file_path, source.markdown_path]:
            if rel_path:
                path = (Path(settings.BASE_DIR) / rel_path).resolve()
                root = self.root.resolve()
                if self._is_child_path(path, root) and path.is_file():
                    path.unlink(missing_ok=True)
        asset_dir = (self.root / "wiki" / "assets" / source.content_hash).resolve()
        asset_root = (self.root / "wiki" / "assets").resolve()
        if self._is_child_path(asset_dir, asset_root) and asset_dir.is_dir():
            shutil.rmtree(asset_dir)
        await source.delete()
        if not await WikiSource.all().exists():
            await self.cleanup_generated_wiki()

    async def cleanup_generated_wiki(self) -> None:
        await self._delete_pages(await WikiPage.all())
        for name in ["sources", "concepts", "entities", "practices", "syntheses", "visual", "queries"]:
            await self._clear_dir(self.root / "wiki" / name)
        for name in ["raw", "markdown"]:
            await self._clear_dir(self.root / name)
        await self._clear_dir(self.root / "wiki" / "assets")
        wiki_builder._write_page("index.md", "# Wiki Index\n")
        wiki_builder._write_page("overview.md", "# Overview\n")

    async def _delete_pages(self, pages: list[WikiPage]) -> None:
        page_ids = [page.id for page in pages]
        if page_ids:
            await WikiLink.filter(from_page_id__in=page_ids).delete()
            await WikiLink.filter(to_page_id__in=page_ids).delete()
        root = (self.root / "wiki").resolve()
        for page in pages:
            if page.path:
                path = (root / page.path).resolve()
                if self._is_child_path(path, root) and path.is_file():
                    path.unlink(missing_ok=True)
        if page_ids:
            await WikiPage.filter(id__in=page_ids).delete()

    async def _clear_dir(self, path: Path) -> None:
        root = self.root.resolve()
        target = path.resolve()
        if not self._is_child_path(target, root):
            return
        target.mkdir(parents=True, exist_ok=True)
        for child in target.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)

    @staticmethod
    def _is_child_path(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True


wiki_import_service = WikiImportService()
