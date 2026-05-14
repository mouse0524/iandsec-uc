from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TerminalAuthReportIn(BaseModel):
    companyName: str = Field(..., min_length=1, max_length=120, description="公司名称")
    authExpireAt: datetime = Field(..., description="授权到期时间")
    maintainExpireAt: datetime = Field(..., description="维保到期时间")
    terminalStats: dict[str, int] = Field(default_factory=dict, description="终端数量统计")
    clientVersions: dict[str, dict[str, int]] = Field(default_factory=dict, description="客户端版本统计")
    serverVersion: str | None = Field(default=None, max_length=120, description="服务器版本号")

    @field_validator("terminalStats")
    @classmethod
    def validate_terminal_stats(cls, value: dict[str, int]):
        return _normalize_number_map(value, allowed_keys={"windows", "mac", "linux", "mobile"})

    @field_validator("clientVersions")
    @classmethod
    def validate_client_versions(cls, value: dict[str, dict[str, int]]):
        normalized: dict[str, dict[str, int]] = {}
        for platform, versions in (value or {}).items():
            key = str(platform or "").strip().lower()
            if key not in {"windows", "mac", "linux", "mobile"}:
                continue
            normalized[key] = _normalize_number_map(versions or {})
        return normalized


class TerminalUpgradeConfigIn(BaseModel):
    latest_version: str = Field(..., min_length=1, max_length=120, description="最新版本号")
    webdav_path: str = Field(..., min_length=1, max_length=1000, description="WebDAV升级包路径")
    enabled: bool = Field(default=True, description="是否启用")
    force_upgrade: bool = Field(default=False, description="是否强制升级")
    release_notes: str | None = Field(default=None, description="版本说明")
    report_token: str | None = Field(default=None, max_length=255, description="第三方上报密钥")
    download_expire_hours: int = Field(default=168, ge=1, le=8760, description="下载链接有效期小时")


class TerminalUpgradeCheckIn(BaseModel):
    currentVersion: str = Field(..., min_length=1, max_length=120, description="当前版本号")
    platform: str | None = Field(default=None, max_length=30, description="终端平台")
    companyName: str | None = Field(default=None, max_length=120, description="公司名称")


def _normalize_number_map(value: dict[str, Any], allowed_keys: set[str] | None = None) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for raw_key, raw_value in (value or {}).items():
        key = str(raw_key or "").strip().lower()
        if not key or (allowed_keys is not None and key not in allowed_keys):
            continue
        try:
            count = int(raw_value or 0)
        except (TypeError, ValueError):
            count = 0
        normalized[key] = max(count, 0)
    return normalized
