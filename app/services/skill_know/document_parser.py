from __future__ import annotations

import re
from pathlib import Path


SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS = {
    "pdf",
    "ppt",
    "pptx",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "html",
    "htm",
    "csv",
    "json",
    "xml",
    "txt",
    "md",
    "markdown",
}

SUPPORTED_MARKDOWN_UPLOAD_MESSAGE = "仅支持 PDF、PowerPoint、Word、Excel、HTML、CSV、JSON、XML、TXT、MD 文件"


class SkillKnowDocumentParser:
    async def convert_to_markdown(self, file_path: str, file_type: str | None = None) -> str:
        ext = (file_type or Path(file_path).suffix).lower().lstrip(".")
        if ext not in SUPPORTED_MARKDOWN_UPLOAD_EXTENSIONS:
            raise ValueError(SUPPORTED_MARKDOWN_UPLOAD_MESSAGE)
        if ext in {"md", "markdown", "txt"}:
            markdown = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        else:
            try:
                from markitdown import MarkItDown

                result = MarkItDown().convert(file_path)
                markdown = result.text_content or ""
            except Exception as exc:
                raise ValueError(f"Markdown 转换失败: {exc}") from exc
        markdown = self._normalize(markdown)
        if not markdown:
            raise ValueError("Markdown 转换结果为空")
        return markdown

    async def parse(self, file_path: str, file_type: str) -> str:
        return await self.convert_to_markdown(file_path, file_type)

    def _normalize(self, markdown: str) -> str:
        value = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"\n{4,}", "\n\n\n", value)
        return value.strip()


skill_know_document_parser = SkillKnowDocumentParser()
