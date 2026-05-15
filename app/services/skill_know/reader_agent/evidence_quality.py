from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceQuality:
    sufficient: bool
    score: float
    reasons: list[str]


class SkillKnowEvidenceQualityService:
    MIN_SCORE = 6.0

    def evaluate(self, question: str, candidates: list[dict], evidence_count: int) -> EvidenceQuality:
        if evidence_count <= 0 or not candidates:
            return EvidenceQuality(False, 0.0, ["没有检索到可用证据"])
        top = candidates[0]
        score = float(top.get("score") or 0)
        matched_terms = top.get("matched_terms") or []
        reasons: list[str] = []
        if score < self.MIN_SCORE:
            reasons.append(f"最高证据分数较低：{score:.2f}")
        if not matched_terms:
            reasons.append("没有核心命中词")
        if any(word in question for word in ("怎么", "如何", "配置", "设置")):
            preview = " ".join(str(item.get("preview") or "") for item in candidates[:3])
            if not any(word in preview for word in ("点击", "选择", "勾选", "配置", "设置", "保存", "推送", "下发", "添加", "进入")):
                reasons.append("证据中缺少明确操作步骤")
        sufficient = not reasons or score >= self.MIN_SCORE + 3
        return EvidenceQuality(sufficient=sufficient, score=score, reasons=reasons)


skill_know_evidence_quality_service = SkillKnowEvidenceQualityService()
