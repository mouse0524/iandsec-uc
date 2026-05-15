import hashlib
import re
import uuid
from datetime import datetime
from typing import Any

from app.models.admin import SkillKnowDocument, SkillKnowFolder


def new_uuid() -> str:
    return str(uuid.uuid4())


def make_uri(kind: str, value: str | int) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value)).strip("-").lower()
    return f"sk://{kind}/{safe or uuid.uuid4().hex}"


def sha256_text(text: str | bytes) -> str:
    if isinstance(text, str):
        text = text.encode("utf-8", errors="ignore")
    return hashlib.sha256(text).hexdigest()


def preview_text(text: str | None, limit: int = 240) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def folder_to_dict(folder: SkillKnowFolder, children: list[dict] | None = None) -> dict:
    data = await folder.to_dict()
    data["children"] = children or []
    return data


async def document_to_dict(document: SkillKnowDocument, *, include_content: bool = True) -> dict[str, Any]:
    data = await document.to_dict()
    if not include_content:
        content = data.pop("content", None) or ""
        data["content_preview"] = preview_text(content, 240)
    return data


