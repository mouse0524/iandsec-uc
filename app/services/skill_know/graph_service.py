from __future__ import annotations

from fastapi import HTTPException
from tortoise.expressions import Q

from app.models.admin import SkillKnowContextRelation, SkillKnowDocument


class SkillKnowGraphService:
    async def record(
        self,
        *,
        source_uri: str,
        target_uri: str,
        relation_type: str = "related_to",
        reason: str = "",
        weight: float = 1.0,
        metadata: dict | None = None,
    ) -> dict:
        if not source_uri or not target_uri:
            raise HTTPException(status_code=400, detail="source_uri 和 target_uri 不能为空")
        relation = await SkillKnowContextRelation.filter(
            source_uri=source_uri,
            target_uri=target_uri,
            relation_type=relation_type,
        ).first()
        if relation:
            relation.reason = reason or relation.reason
            relation.weight = weight
            relation.extra_metadata = metadata or relation.extra_metadata or {}
            await relation.save()
        else:
            relation = await SkillKnowContextRelation.create(
                source_uri=source_uri,
                target_uri=target_uri,
                relation_type=relation_type,
                reason=reason,
                weight=weight,
                extra_metadata=metadata or {},
            )
        return await relation.to_dict()

    async def delete(self, relation_id: int) -> None:
        deleted = await SkillKnowContextRelation.filter(id=relation_id).delete()
        if not deleted:
            raise HTTPException(status_code=404, detail="关系不存在")

    async def cleanup_uri(self, uri: str) -> None:
        await SkillKnowContextRelation.filter(Q(source_uri=uri) | Q(target_uri=uri)).delete()

    async def graph(self, *, center_uri: str | None = None, depth: int = 2, limit: int = 200) -> dict:
        q = Q()
        if center_uri:
            q &= Q(source_uri=center_uri) | Q(target_uri=center_uri)
        relations = await SkillKnowContextRelation.filter(q).order_by("-weight", "-id").limit(limit)
        uri_set = {rel.source_uri for rel in relations} | {rel.target_uri for rel in relations}
        nodes = await self._nodes(uri_set)
        edges = [
            {
                "id": rel.id,
                "source": rel.source_uri,
                "target": rel.target_uri,
                "type": rel.relation_type,
                "label": rel.relation_type,
                "reason": rel.reason,
                "weight": rel.weight,
            }
            for rel in relations
        ]
        return {"nodes": list(nodes.values()), "edges": edges, "total": len(edges)}

    async def _nodes(self, uris: set[str]) -> dict[str, dict]:
        nodes: dict[str, dict] = {}
        if not uris:
            return nodes
        documents = await SkillKnowDocument.filter(uri__in=list(uris))
        for doc in documents:
            nodes[doc.uri] = {
                "id": doc.uri,
                "uri": doc.uri,
                "label": doc.title,
                "type": "document",
                "category": doc.category,
                "abstract": doc.abstract or doc.description,
            }
        for uri in uris:
            nodes.setdefault(uri, {"id": uri, "uri": uri, "label": uri.split("/")[-1], "type": "context"})
        return nodes


skill_know_graph_service = SkillKnowGraphService()
