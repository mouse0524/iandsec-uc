from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.log import logger


DEFAULT_DOMAIN_TERMS: dict[str, Any] = {
    "version": 1,
    "stopwords": [
        "的",
        "了",
        "吗",
        "呢",
        "啊",
        "是",
        "有",
        "请问",
        "帮我",
        "一个",
        "什么",
        "怎么",
        "如何",
        "多少",
        "哪里",
        "在哪",
        "在哪里",
        "基于",
        "上面",
        "回答",
        "继续",
        "说明",
        "我要",
        "给我",
        "详细",
        "进行",
    ],
    "followup_noise": [
        "请基于上面的回答继续说明",
        "基于上面的回答继续说明",
        "请基于上面回答继续说明",
        "基于上面回答继续说明",
        "上面的回答",
        "上面回答",
    ],
    "weak_terms": ["配置", "设置", "开启", "选择", "点击", "保存", "推送", "下发", "添加", "启用", "策略", "加密", "解密"],
    "config_hints": ["策略配置", "配置", "开启", "勾选", "选择", "点击", "保存", "推送", "下发", "添加", "设置", "启用"],
    "password_hints": ["账号", "密码", "默认", "初始", "sysadmin", "secadmin", "logadmin"],
    "trouble_hints": ["报错", "失败", "无法", "异常", "原因", "处理", "解决", "日志"],
    "synonyms": {
        "落地解密": ["落地加密", "加解密", "加解密类型", "策略配置", "透明加解密"],
        "落地加密": ["落地解密", "加解密", "加解密类型", "策略配置", "透明加解密"],
        "透明解密": ["透明加解密", "加解密", "加解密类型", "策略配置"],
        "透明加密": ["透明加解密", "加解密", "加解密类型", "策略配置"],
        "透明加解密": ["加解密", "加解密类型", "策略配置"],
        "解密": ["加解密", "加解密类型"],
        "加密": ["加解密", "加解密类型"],
        "共享盘": ["共享目录", "网络盘", "网络路径", "地址", "例外目录"],
        "全盘": ["全盘扫描", "文件类型", "例外目录", "策略配置"],
        "U盘": ["移动客户端", "移动设备", "介质", "注册"],
        "注册U盘": ["移动客户端", "移动设备", "介质注册", "授权"],
        "网关": ["安全网关", "准入网关", "加解密网关", "网关配置", "网络配置"],
        "安全网关": ["准入网关", "加解密网关", "网关配置", "网络配置"],
        "WPS": ["wps", "金山WPS", "WPS策略", "WPS老板策略"],
    },
}


class SkillKnowDomainTerms:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path("storage") / "skill_know" / "domain_terms.json")
        self.data = DEFAULT_DOMAIN_TERMS
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self.data = DEFAULT_DOMAIN_TERMS
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = self._merge(DEFAULT_DOMAIN_TERMS, loaded)
        except Exception as exc:
            logger.warning("[skill_know.domain_terms.load_failed] path={} error={}", str(self.path), str(exc))
            self.data = DEFAULT_DOMAIN_TERMS

    def _merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in (override or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                merged = dict(result[key])
                merged.update(value)
                result[key] = merged
            else:
                result[key] = value
        return result

    @property
    def version(self) -> int:
        return int(self.data.get("version") or 1)

    def list_value(self, key: str) -> list[str]:
        value = self.data.get(key) or []
        return [str(item) for item in value if str(item).strip()]

    @property
    def synonyms(self) -> dict[str, list[str]]:
        raw = self.data.get("synonyms") or {}
        return {str(key): [str(item) for item in values] for key, values in raw.items() if isinstance(values, list)}


skill_know_domain_terms = SkillKnowDomainTerms()
