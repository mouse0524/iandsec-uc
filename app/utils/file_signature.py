from __future__ import annotations

import zipfile


FILE_SIGNATURES: dict[str, list[bytes]] = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    "rar": [b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00"],
}
OOXML_EXTENSIONS = {"docx", "pptx", "xlsx"}
OOXML_MARKERS = {
    "docx": "word/",
    "pptx": "ppt/",
    "xlsx": "xl/",
}


def normalize_ext(filename: str) -> str:
    if not filename:
        return ""
    dot = filename.rfind(".")
    if dot < 0:
        return ""
    return filename[dot + 1 :].strip().lower()


def _detect_ooxml_type(path: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return None

    if "[Content_Types].xml" not in names:
        return None
    for ext, marker in OOXML_MARKERS.items():
        if any(name.startswith(marker) for name in names):
            return ext
    return None


def detect_file_type(data: bytes, filename: str | None = None, path: str | None = None) -> str | None:
    ext = normalize_ext(filename or path or "")
    zip_magic = any(data.startswith(signature) for signature in FILE_SIGNATURES["zip"])
    if zip_magic and ext in OOXML_EXTENSIONS and path:
        detected = _detect_ooxml_type(path)
        if detected:
            return detected
    if ext in FILE_SIGNATURES and any(data.startswith(signature) for signature in FILE_SIGNATURES[ext]):
        return ext

    for file_type, signatures in FILE_SIGNATURES.items():
        if any(data.startswith(signature) for signature in signatures):
            return file_type

    # WEBP magic: RIFF....WEBP
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"

    return None
