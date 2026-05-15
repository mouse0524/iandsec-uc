import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.skill_know.eval_service import SkillKnowEvalCase, SkillKnowEvalService
from app.services.skill_know.retrieval_debug_service import SkillKnowRetrievalDebugService
from app.services.skill_know.reader_agent.whoosh_search import SkillKnowWhooshSearch


class SkillKnowWhooshSearchTestCase(unittest.TestCase):
    def test_whoosh_search_rebuild_search_and_delete_document(self):
        async def run():
            with tempfile.TemporaryDirectory() as tmp:
                search = SkillKnowWhooshSearch(Path(tmp) / "reader_whoosh")
                await search.rebuild_document(
                    7,
                    [
                        {
                            "section_id": 101,
                            "title": "安得产品使用手册",
                            "filename": "manual.docx",
                            "heading": "透明加解密",
                            "heading_path": "文件加密服务 / 策略配置 / 透明加解密",
                            "keywords": ["落地加密", "策略配置"],
                            "text": "进入策略配置页面，勾选落地加密，开启加解密类型，保存并推送策略。",
                            "start_line": 10,
                            "end_line": 20,
                        }
                    ],
                )

                hits = await search.search(["透明加解密", "落地加密"], limit=5)
                await search.delete_document(7)
                deleted_hits = await search.search(["透明加解密"], limit=5)
                search.reset()
                return hits, deleted_hits

        hits, deleted_hits = asyncio.run(run())

        self.assertEqual([hit.section_id for hit in hits], [101])
        self.assertEqual([hit.document_id for hit in hits], [7])
        self.assertEqual(deleted_hits, [])

    def test_whoosh_require_all_filters_partial_matches(self):
        async def run():
            with tempfile.TemporaryDirectory() as tmp:
                search = SkillKnowWhooshSearch(Path(tmp) / "reader_whoosh")
                await search.rebuild_document(
                    8,
                    [
                        {
                            "section_id": 201,
                            "title": "产品手册",
                            "filename": "manual.docx",
                            "heading": "透明加解密",
                            "heading_path": "策略配置 / 透明加解密",
                            "keywords": ["透明加解密", "落地加密"],
                            "text": "勾选落地加密后保存并推送策略。",
                            "start_line": 1,
                            "end_line": 5,
                        },
                        {
                            "section_id": 202,
                            "title": "产品手册",
                            "filename": "manual.docx",
                            "heading": "透明加解密",
                            "heading_path": "策略配置 / 透明加解密",
                            "keywords": ["透明加解密"],
                            "text": "只介绍透明加解密入口。",
                            "start_line": 6,
                            "end_line": 10,
                        },
                    ],
                )
                return await search.search(["透明加解密", "落地加密"], limit=5, require_all=True)

        hits = asyncio.run(run())

        self.assertEqual([hit.section_id for hit in hits], [201])

    def test_eval_service_reports_matching_rank(self):
        async def run():
            with patch(
                "app.services.skill_know.eval_service.skill_know_reader_tools.search_sections",
                AsyncMock(
                    return_value=[
                        {"section_id": 1, "document_id": 10, "heading": "其他", "heading_path": "其他"},
                        {"section_id": 2, "document_id": 20, "heading": "透明加解密", "heading_path": "策略配置 / 透明加解密"},
                    ]
                ),
            ):
                return await SkillKnowEvalService().evaluate_case(
                    SkillKnowEvalCase(question="透明加解密怎么配置", expected_document_id=20, expected_heading_contains="透明加解密"),
                    top_k=3,
                )

        result = asyncio.run(run())

        self.assertEqual(result["matched_rank"], 2)
        self.assertFalse(result["top1_hit"])
        self.assertTrue(result["top3_hit"])

    def test_retrieval_debug_service_returns_terms_and_candidates(self):
        async def run():
            with patch(
                "app.services.skill_know.retrieval_debug_service.skill_know_reader_tools.debug_search",
                AsyncMock(return_value={"query": "网关怎么配置", "terms": ["网关"], "strong_terms": ["网关"], "items": [], "candidates": []}),
            ):
                return await SkillKnowRetrievalDebugService().debug("网关怎么配置", top_k=5)

        result = asyncio.run(run())

        self.assertEqual(result["query"], "网关怎么配置")
        self.assertEqual(result["strong_terms"], ["网关"])
        self.assertIn("domain_terms_version", result)


if __name__ == "__main__":
    unittest.main()
