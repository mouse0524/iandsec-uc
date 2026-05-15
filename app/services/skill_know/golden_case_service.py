from __future__ import annotations

import json
from pathlib import Path

from app.schemas.skill_know import SkillKnowGoldenCaseIn
from app.services.skill_know.utils import new_uuid


DEFAULT_GOLDEN_CASES = [
    {"id": "default-landing-decrypt", "question": "落地解密在哪里配置", "expected_heading_contains": "加解密", "enabled": True},
    {"id": "default-share-landing", "question": "共享盘全盘落地解密怎么配置", "expected_heading_contains": "加解密", "enabled": True},
    {"id": "default-transparent", "question": "透明加解密怎么配置", "expected_heading_contains": "加解密", "enabled": True},
    {"id": "default-wps", "question": "WPS加密策略怎么配置", "expected_heading_contains": "WPS", "enabled": True},
    {"id": "default-usb-register", "question": "注册U盘不生效怎么排查", "expected_heading_contains": "移动", "enabled": True},
    {"id": "default-usb-key", "question": "U盘客户端导出key在哪里", "expected_heading_contains": "移动", "enabled": True},
    {"id": "default-gateway", "question": "网关怎么配置", "expected_heading_contains": "网关", "enabled": True},
    {"id": "default-sysadmin-password", "question": "管理员sysadmin的密码是多少", "expected_heading_contains": "密码", "enabled": True},
]


class SkillKnowGoldenCaseService:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path("storage") / "skill_know" / "golden_cases.json")

    def list_cases(self, *, enabled_only: bool = False) -> list[dict]:
        rows = self._load()
        if enabled_only:
            rows = [item for item in rows if item.get("enabled", True)]
        return rows

    def upsert(self, payload: SkillKnowGoldenCaseIn) -> dict:
        rows = self._load()
        data = payload.model_dump()
        data["id"] = data.get("id") or new_uuid()
        for index, row in enumerate(rows):
            if row.get("id") == data["id"]:
                rows[index] = data
                self._save(rows)
                return data
        rows.append(data)
        self._save(rows)
        return data

    def delete(self, case_id: str) -> None:
        rows = [item for item in self._load() if item.get("id") != case_id]
        self._save(rows)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return [dict(item) for item in DEFAULT_GOLDEN_CASES]
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            return [dict(item) for item in DEFAULT_GOLDEN_CASES]
        return [dict(item) for item in DEFAULT_GOLDEN_CASES]

    def _save(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


skill_know_golden_case_service = SkillKnowGoldenCaseService()
