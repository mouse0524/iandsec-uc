from datetime import datetime, timezone
import re

from fastapi import HTTPException

from app.controllers.webdav import webdav_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import TerminalAuthReport, TerminalUpgradeConfig
from app.schemas.terminal import TerminalAuthReportIn, TerminalUpgradeCheckIn, TerminalUpgradeConfigIn
from app.settings import settings


class TerminalService:
    PLATFORMS = ("windows", "mac", "linux", "mobile")

    async def report_auth(self, payload: TerminalAuthReportIn, *, source_ip: str | None, token: str | None) -> dict:
        await self._verify_report_token(token)
        row = await TerminalAuthReport.create(
            company_name=payload.companyName.strip(),
            auth_expire_at=payload.authExpireAt,
            maintain_expire_at=payload.maintainExpireAt,
            terminal_stats=self._normalize_terminal_stats(payload.terminalStats),
            client_versions=self._normalize_client_versions(payload.clientVersions),
            server_version=(payload.serverVersion or "").strip() or None,
            reported_at=datetime.now(timezone.utc),
            source_ip=source_ip,
            raw_payload=payload.model_dump(mode="json"),
        )
        logger.info("[terminal.auth.report] id={} company={} source_ip={}", row.id, row.company_name, source_ip)
        return self._report_to_dict(row)

    async def list_auth_reports(
        self,
        *,
        page: int,
        page_size: int,
        company_name: str | None = None,
    ) -> tuple[int, list[dict]]:
        query = TerminalAuthReport.all()
        keyword = (company_name or "").strip()
        if keyword:
            query = query.filter(company_name__icontains=keyword)
        query = query.order_by("-reported_at", "-id")
        total = await query.count()
        rows = await query.offset((page - 1) * page_size).limit(page_size)
        return total, [self._report_to_dict(row) for row in rows]

    async def latest_auth_report(self, *, company_name: str | None = None) -> dict | None:
        query = TerminalAuthReport.all()
        if company_name:
            query = query.filter(company_name=company_name)
        row = await query.order_by("-reported_at", "-id").first()
        return self._report_to_dict(row) if row else None

    async def get_upgrade_config(self) -> dict | None:
        row = await TerminalUpgradeConfig.all().order_by("-id").first()
        return self._upgrade_to_dict(row, include_token=True) if row else None

    async def save_upgrade_config(self, payload: TerminalUpgradeConfigIn) -> dict:
        row = await TerminalUpgradeConfig.all().order_by("-id").first()
        data = payload.model_dump()
        data["latest_version"] = data["latest_version"].strip()
        data["webdav_path"] = webdav_controller._normalize_path(data["webdav_path"])
        if data.get("report_token") == "******" and row:
            data["report_token"] = row.report_token
        if row:
            await row.update_from_dict(data).save()
        else:
            row = await TerminalUpgradeConfig.create(**data)
        logger.info("[terminal.upgrade.config.save] id={} version={} path={}", row.id, row.latest_version, row.webdav_path)
        return self._upgrade_to_dict(row, include_token=True)

    async def check_upgrade(self, payload: TerminalUpgradeCheckIn) -> dict:
        row = await TerminalUpgradeConfig.filter(enabled=True).order_by("-id").first()
        if not row:
            return {"upgrade": False, "reason": "upgrade_disabled"}

        current_version = (payload.currentVersion or "").strip()
        latest_version = (row.latest_version or "").strip()
        upgrade = self._compare_versions(current_version, latest_version) < 0
        result = {
            "upgrade": upgrade,
            "currentVersion": current_version,
            "latestVersion": latest_version,
            "releaseNotes": row.release_notes or "",
            "serverTime": datetime.now(timezone.utc).strftime(settings.DATETIME_FORMAT),
        }
        if upgrade:
            result["downloadUrl"] = await self._build_upgrade_download_url(row)
            result["webdavPath"] = row.webdav_path
        return result

    async def _build_upgrade_download_url(self, row: TerminalUpgradeConfig) -> str:
        cache_key = f"terminal:upgrade:download:{row.id}:{row.latest_version}:{row.webdav_path}:{row.download_expire_hours}"
        try:
            cached = await execute_redis("get", cache_key)
            if cached:
                return str(cached)
        except Exception as exc:
            logger.warning("[terminal.upgrade.download.cache_get_failed] key={} error={}", cache_key, str(exc))

        url = await webdav_controller.get_direct_download_url(row.webdav_path)
        ttl_seconds = max(60, min(int(row.download_expire_hours or 1) * 3600, 24 * 3600))
        try:
            await execute_redis("setex", cache_key, ttl_seconds, url)
        except Exception as exc:
            logger.warning("[terminal.upgrade.download.cache_set_failed] key={} error={}", cache_key, str(exc))
        return url

    async def _verify_report_token(self, token: str | None) -> None:
        row = await TerminalUpgradeConfig.all().order_by("-id").first()
        expected = (row.report_token or "").strip() if row else ""
        if not expected:
            return
        if (token or "").strip() != expected:
            raise HTTPException(status_code=401, detail="终端上报密钥校验失败")

    def _report_to_dict(self, row: TerminalAuthReport) -> dict:
        terminal_stats = self._normalize_terminal_stats(row.terminal_stats or {})
        client_versions = self._normalize_client_versions(row.client_versions or {})
        data = {
            "id": row.id,
            "company_name": row.company_name,
            "auth_expire_at": self._fmt_dt(row.auth_expire_at),
            "maintain_expire_at": self._fmt_dt(row.maintain_expire_at),
            "terminal_stats": terminal_stats,
            "terminal_stats_text": self._terminal_stats_text(terminal_stats),
            "client_versions": client_versions,
            "client_versions_text": self._client_versions_text(client_versions),
            "server_version": row.server_version or "",
            "reported_at": self._fmt_dt(row.reported_at),
            "source_ip": row.source_ip or "",
            "created_at": self._fmt_dt(row.created_at),
            "updated_at": self._fmt_dt(row.updated_at),
        }
        return data

    def _upgrade_to_dict(self, row: TerminalUpgradeConfig, *, include_token: bool = False) -> dict:
        data = {
            "id": row.id,
            "latest_version": row.latest_version,
            "webdav_path": row.webdav_path,
            "enabled": row.enabled,
            "release_notes": row.release_notes or "",
            "download_expire_hours": row.download_expire_hours,
            "created_at": self._fmt_dt(row.created_at),
            "updated_at": self._fmt_dt(row.updated_at),
        }
        if include_token:
            data["report_token"] = "******" if row.report_token else ""
        return data

    def _normalize_terminal_stats(self, stats: dict) -> dict[str, int]:
        return {key: max(int((stats or {}).get(key) or 0), 0) for key in self.PLATFORMS}

    def _normalize_client_versions(self, versions: dict) -> dict[str, dict[str, int]]:
        normalized: dict[str, dict[str, int]] = {}
        for platform in self.PLATFORMS:
            rows = {}
            for version, count in ((versions or {}).get(platform) or {}).items():
                key = str(version or "").strip()
                if not key:
                    continue
                try:
                    rows[key] = max(int(count or 0), 0)
                except (TypeError, ValueError):
                    rows[key] = 0
            normalized[platform] = rows
        return normalized

    @staticmethod
    def _terminal_stats_text(stats: dict[str, int]) -> str:
        return f"windows：{stats.get('windows', 0)} mac：{stats.get('mac', 0)} linux：{stats.get('linux', 0)} 手机：{stats.get('mobile', 0)}"

    @staticmethod
    def _client_versions_text(versions: dict[str, dict[str, int]]) -> str:
        totals: dict[str, int] = {}
        for platform_versions in versions.values():
            for version, count in platform_versions.items():
                totals[version] = totals.get(version, 0) + int(count or 0)
        if not totals:
            return "-"
        return "，".join(f"{version}：{count}" for version, count in sorted(totals.items()))

    @staticmethod
    def _fmt_dt(value) -> str:
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime(settings.DATETIME_FORMAT)
        return str(value)

    @staticmethod
    def _compare_versions(current: str, latest: str) -> int:
        def parts(value: str) -> list[int | str]:
            tokens = re.split(r"([0-9]+)", value or "")
            result: list[int | str] = []
            for token in tokens:
                if not token:
                    continue
                result.append(int(token) if token.isdigit() else token.lower())
            return result

        left = parts(current)
        right = parts(latest)
        for idx in range(max(len(left), len(right))):
            a = left[idx] if idx < len(left) else 0
            b = right[idx] if idx < len(right) else 0
            if a == b:
                continue
            if isinstance(a, int) and isinstance(b, int):
                return -1 if a < b else 1
            return -1 if str(a) < str(b) else 1
        return 0


terminal_service = TerminalService()
