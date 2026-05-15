import asyncio
import base64
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.services.skill_know.document_service import SkillKnowDocumentService
from app.services.skill_know.document_text import normalize_document_text
from app.services.skill_know.reader_agent.agent_service import SkillKnowReaderAgentService
from app.services.skill_know.reader_agent.reader_tools import SkillKnowReaderTools
from app.services.skill_know.reader_agent.section_indexer import SkillKnowSectionIndexer
from app.core.ctx import CTX_USER_ID


class SkillKnowDocumentServiceTestCase(unittest.TestCase):
    def test_skill_know_upload_limit_is_one_gb(self):
        self.assertEqual(SkillKnowDocumentService.MAX_UPLOAD_SIZE, 1024 * 1024 * 1024)

    def test_max_total_chunks_allows_one_gb_with_two_mb_chunks(self):
        self.assertGreaterEqual(SkillKnowDocumentService.MAX_TOTAL_CHUNKS, 512)

    def test_asset_path_rejects_traversal(self):
        service = SkillKnowDocumentService()
        with self.assertRaises(HTTPException):
            service._asset_path("doc-uuid", "../secret.png")

    def test_asset_url_is_scoped_to_document(self):
        service = SkillKnowDocumentService()
        self.assertEqual(
            service._asset_url(42, "image 1.png"),
            "/skill-know/documents/assets/42/image%201.png",
        )

    def test_markdown_asset_paths_are_rewritten_to_document_urls(self):
        service = SkillKnowDocumentService()
        markdown = "![流程图](diagram.png)\n![远程](https://example.com/a.png)"

        rewritten = service._rewrite_markdown_asset_paths(markdown, document_id=7)

        self.assertIn("![流程图](/skill-know/documents/assets/7/diagram.png)", rewritten)
        self.assertIn("![远程](https://example.com/a.png)", rewritten)

    def test_data_uri_images_are_saved_as_document_assets(self):
        service = SkillKnowDocumentService()
        png_data = base64.b64encode(b"png-bytes").decode("ascii")
        markdown = f"![截图](data:image/png;base64,{png_data})"

        with patch.object(service, "_asset_dir") as asset_dir:
            path = MagicMock()
            path.exists.return_value = False
            path.write_bytes = MagicMock()
            asset_dir.return_value.__truediv__.return_value = path
            rewritten = service._materialize_data_uri_images(markdown, document_id=9, document_uuid="doc-uuid")

        path.write_bytes.assert_called_once_with(b"png-bytes")
        self.assertEqual(rewritten, "![截图](/skill-know/documents/assets/9/image-1.png)")

    def test_html_data_uri_images_are_saved_as_document_assets(self):
        service = SkillKnowDocumentService()
        png_data = base64.b64encode(b"html-png-bytes").decode("ascii")
        markdown = f'<p><img alt="截图" src="data:image/png;base64,{png_data}" /></p>'

        with patch.object(service, "_asset_dir") as asset_dir:
            path = MagicMock()
            path.exists.return_value = False
            path.write_bytes = MagicMock()
            asset_dir.return_value.__truediv__.return_value = path
            rewritten = service._materialize_data_uri_images(markdown, document_id=9, document_uuid="doc-uuid")

        path.write_bytes.assert_called_once_with(b"html-png-bytes")
        self.assertEqual(
            rewritten,
            '<p><img alt="截图" src="/skill-know/documents/assets/9/image-1.png" /></p>',
        )

    def test_markdown_local_images_are_copied_to_document_assets(self):
        service = SkillKnowDocumentService()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "doc.md"
            image = Path(temp_dir) / "images" / "diagram.png"
            image.parent.mkdir()
            image.write_bytes(b"diagram-bytes")
            source.write_text("![流程](images/diagram.png)", encoding="utf-8")

            with patch.object(service, "_asset_dir") as asset_dir:
                target_dir = Path(temp_dir) / "assets"
                target_dir.mkdir()
                asset_dir.return_value = target_dir
                rewritten = service._materialize_local_markdown_images(
                    source.read_text(encoding="utf-8"),
                    str(source),
                    document_id=10,
                    document_uuid="doc-uuid",
                )
            copied = (target_dir / "diagram.png").read_bytes()

        self.assertEqual(rewritten, "![流程](/skill-know/documents/assets/10/diagram.png)")
        self.assertEqual(copied, b"diagram-bytes")

    def test_html_local_images_are_copied_to_document_assets(self):
        service = SkillKnowDocumentService()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "doc.md"
            image = Path(temp_dir) / "images" / "chart.png"
            image.parent.mkdir()
            image.write_bytes(b"chart-bytes")
            source.write_text('<img src="images/chart.png" alt="图表">', encoding="utf-8")

            with patch.object(service, "_asset_dir") as asset_dir:
                target_dir = Path(temp_dir) / "assets"
                target_dir.mkdir()
                asset_dir.return_value = target_dir
                rewritten = service._materialize_local_markdown_images(
                    source.read_text(encoding="utf-8"),
                    str(source),
                    document_id=11,
                    document_uuid="doc-uuid",
                )
            copied = (target_dir / "chart.png").read_bytes()

        self.assertEqual(
            rewritten,
            '<img src="/skill-know/documents/assets/11/chart.png" alt="图表">',
        )
        self.assertEqual(copied, b"chart-bytes")

    def test_local_image_materialization_skips_remote_and_parent_paths(self):
        service = SkillKnowDocumentService()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "docs" / "doc.md"
            source.parent.mkdir()
            secret = Path(temp_dir) / "secret.png"
            secret.write_bytes(b"secret-bytes")
            markdown = "![远程](https://example.com/a.png)\n![越界](../secret.png)"

            with patch.object(service, "_asset_dir") as asset_dir:
                target_dir = Path(temp_dir) / "assets"
                target_dir.mkdir()
                asset_dir.return_value = target_dir
                rewritten = service._materialize_local_markdown_images(
                    markdown,
                    str(source),
                    document_id=12,
                    document_uuid="doc-uuid",
                )
            copied_files = list(target_dir.iterdir())

        self.assertEqual(rewritten, markdown)
        self.assertEqual(copied_files, [])

    def test_office_media_images_are_extracted_for_docx_xlsx_and_pptx(self):
        service = SkillKnowDocumentService()
        media_paths = {
            "docx": "word/media/image1.png",
            "xlsx": "xl/media/image2.jpeg",
            "pptx": "ppt/media/image3.gif",
        }

        for ext, media_path in media_paths.items():
            with self.subTest(ext=ext):
                source = service._temp_dir() + f"/office-media-test.{ext}"
                with zipfile.ZipFile(source, "w") as archive:
                    archive.writestr(media_path, b"image-bytes")

                with patch.object(service, "_asset_dir") as asset_dir:
                    target = MagicMock()
                    target.exists.return_value = False
                    target.write_bytes = MagicMock()
                    asset_dir.return_value.__truediv__.return_value = target
                    markdown = service._append_office_media_images(
                        "# 文档",
                        source,
                        ext,
                        document_id=12,
                        document_uuid="doc-uuid",
                    )

                target.write_bytes.assert_called_once_with(b"image-bytes")
                self.assertIn("# 文档", markdown)
                self.assertIn("/skill-know/documents/assets/12/", markdown)

    def test_pptx_media_images_are_inserted_in_slide_order(self):
        service = SkillKnowDocumentService()
        slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>第一页标题</a:t></a:r></a:p></p:txBody></p:sp>
    <p:pic><p:blipFill><a:blip r:embed="rId2"/></p:blipFill></p:pic>
    <p:sp><p:txBody><a:p><a:r><a:t>图片之后的文字</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>"""
        rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "deck.pptx"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("ppt/slides/slide1.xml", slide_xml)
                archive.writestr("ppt/slides/_rels/slide1.xml.rels", rels_xml)
                archive.writestr("ppt/media/image1.png", b"image-bytes")

            with patch.object(service, "_asset_dir") as asset_dir:
                target_dir = Path(temp_dir) / "assets"
                target_dir.mkdir()
                asset_dir.return_value = target_dir
                markdown = service._inline_office_media_images(
                    "",
                    str(source),
                    "pptx",
                    document_id=20,
                    document_uuid="doc-uuid",
                )

        self.assertLess(markdown.index("第一页标题"), markdown.index("![image1.png]"))
        self.assertLess(markdown.index("![image1.png]"), markdown.index("图片之后的文字"))
        self.assertIn("/skill-know/documents/assets/20/pptx-image-1.png", markdown)

    def test_xlsx_images_are_inserted_after_anchor_row(self):
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image
        from PIL import Image as PILImage

        service = SkillKnowDocumentService()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "source.png"
            PILImage.new("RGB", (2, 2), color="red").save(image_path)
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Sheet1"
            sheet["A1"] = "标题"
            sheet["A2"] = "图片前"
            sheet["A3"] = "图片所在行"
            sheet.add_image(Image(str(image_path)), "A3")
            sheet["A4"] = "图片后"
            source = Path(temp_dir) / "book.xlsx"
            workbook.save(source)

            with patch.object(service, "_asset_dir") as asset_dir:
                target_dir = Path(temp_dir) / "assets"
                target_dir.mkdir()
                asset_dir.return_value = target_dir
                markdown = service._xlsx_to_markdown_with_inline_images(
                    str(source),
                    document_id=21,
                    document_uuid="doc-uuid",
                )

        self.assertLess(markdown.index("图片所在行"), markdown.index("![xlsx-image-1.png]"))
        self.assertLess(markdown.index("![xlsx-image-1.png]"), markdown.index("图片后"))
        self.assertIn("/skill-know/documents/assets/21/xlsx-image-1.png", markdown)

    def test_get_uses_chunk_pagination(self):
        service = SkillKnowDocumentService()
        document = MagicMock(id=1)
        query = MagicMock()
        query.order_by.return_value = query
        query.count = AsyncMock(return_value=25)
        query.offset.return_value = query
        query.limit = AsyncMock()
        chunks = [MagicMock() for _ in range(10)]
        for index, chunk in enumerate(chunks):
            chunk.to_dict = AsyncMock(return_value={"id": index + 11, "chunk_index": index + 10})
        query.limit.return_value = chunks

        async def run():
            token = CTX_USER_ID.set(1)
            with (
                patch("app.services.skill_know.document_service.SkillKnowDocument.filter") as document_filter,
                patch("app.services.skill_know.document_service.SkillKnowDocumentChunk.filter", return_value=query),
                patch("app.services.skill_know.document_service.document_to_dict", AsyncMock(return_value={"id": 1})),
            ):
                try:
                    document_filter.return_value.first = AsyncMock(return_value=document)
                    return await service.get(1, chunk_page=2, chunk_page_size=10)
                finally:
                    CTX_USER_ID.reset(token)

        data = asyncio.run(run())

        self.assertEqual(data["chunk_total"], 25)
        self.assertEqual(data["chunk_page"], 2)
        self.assertEqual(data["chunk_page_size"], 10)
        query.offset.assert_called_once_with(10)
        query.limit.assert_called_once_with(10)

    def test_asset_lookup_keeps_owner_filter(self):
        service = SkillKnowDocumentService()
        document = MagicMock(uuid="doc-uuid")

        async def run():
            token = CTX_USER_ID.set(1)
            with (
                patch("app.services.skill_know.document_service.SkillKnowDocument.filter") as document_filter,
                patch.object(service, "_asset_path") as asset_path,
            ):
                try:
                    path = MagicMock()
                    path.exists.return_value = True
                    path.is_file.return_value = True
                    asset_path.return_value = path
                    document_filter.return_value.first = AsyncMock(return_value=document)
                    result = await service.get_asset(1, "image.png")
                finally:
                    CTX_USER_ID.reset(token)
            return result, document_filter

        result, document_filter = asyncio.run(run())

        self.assertTrue(result.exists())
        document_filter.assert_called_once_with(id=1, owner_id=1)

    def test_section_indexer_parses_heading_sections_with_line_ranges(self):
        indexer = SkillKnowSectionIndexer()
        lines = [
            "# 服务端操作说明",
            "目录",
            "## 透明加解密",
            "进入到策略配置页面。",
            "开启加解密类型，保存并推送策略。",
            "## WPS老板策略",
            "勾选金山WPS策略。",
        ]

        sections = indexer.parse_sections(lines)

        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[1].heading, "透明加解密")
        self.assertEqual(sections[1].heading_path, "服务端操作说明 / 透明加解密")
        self.assertEqual((sections[1].start_line, sections[1].end_line), (3, 5))
        self.assertIn("透明加解密", sections[1].keywords)

    def test_html_content_is_normalized_for_reader_index(self):
        html = """
        <h1>服务端操作说明</h1>
        <p>目录</p>
        <h2>透明加解密</h2>
        <p>进入到策略配置页面。</p>
        <ul><li>开启加解密类型</li><li>保存并推送策略</li></ul>
        <table><tr><th>项目</th><th>说明</th></tr><tr><td>WPS</td><td>勾选金山WPS策略</td></tr></table>
        """

        text = normalize_document_text(html)
        sections = SkillKnowSectionIndexer().parse_sections(text.splitlines())

        self.assertIn("# 服务端操作说明", text)
        self.assertIn("## 透明加解密", text)
        self.assertIn("- 开启加解密类型", text)
        self.assertIn("项目 | 说明", text)
        self.assertEqual(sections[1].heading, "透明加解密")
        self.assertIn("保存并推送策略", sections[1].text)

    def test_reader_tools_prioritize_strong_terms_over_generic_config_words(self):
        tools = SkillKnowReaderTools()

        terms = tools.terms("透明加解密怎么配置")

        self.assertLess(terms.index("透明加解密"), terms.index("配置"))
        self.assertIn("加解密", terms)
        self.assertNotIn("怎么配置", terms)

    def test_reader_tools_score_prefers_exact_heading_match(self):
        tools = SkillKnowReaderTools()
        exact = MagicMock(
            heading="透明加解密",
            heading_path="文件加密服务 / 策略配置 / 透明加解密",
            text_preview="进入到策略配置页面，开启加解密类型，保存并推送策略。",
            text="进入到策略配置页面，开启加解密类型，保存并推送策略。",
            keywords=["透明加解密", "策略配置"],
        )
        generic = MagicMock(
            heading="流程辅助控制",
            heading_path="文件解密流程 / 流程辅助控制",
            text_preview="本地解密成明文，解密后带压缩密码。",
            text="本地解密成明文，解密后带压缩密码。",
            keywords=["解密", "密码"],
        )
        terms = tools.terms("透明加解密怎么配置")

        exact_score, _ = tools._score_section("透明加解密怎么配置", exact, terms)
        generic_score, _ = tools._score_section("透明加解密怎么配置", generic, terms)

        self.assertGreater(exact_score, generic_score)

    def test_reader_tools_expands_landing_decrypt_to_policy_terms(self):
        tools = SkillKnowReaderTools()

        terms = tools.terms("落地解密在哪里配置")

        self.assertIn("落地解密", terms)
        self.assertIn("落地加密", terms)
        self.assertIn("加解密类型", terms)
        self.assertIn("策略配置", terms)

    def test_reader_tools_keeps_domain_terms_for_long_followup_query(self):
        tools = SkillKnowReaderTools()

        terms = tools.terms("请基于上面的回答继续说明：我要对共享盘192.168.10.100进行全盘落地解密，给我详细的策略配置")

        self.assertLess(terms.index("落地解密"), 8)
        self.assertLess(terms.index("加解密类型"), 8)
        self.assertIn("共享盘", terms)
        self.assertIn("网络路径", terms)
        self.assertIn("全盘", terms)
        self.assertIn("文件类型", terms)
        self.assertNotIn("请基于上面回答继续说明", terms)

    def test_reader_tools_score_prefers_landing_policy_section(self):
        tools = SkillKnowReaderTools()
        policy = MagicMock(
            heading="透明加解密",
            heading_path="文件加密服务 / 策略配置 / 透明加解密",
            text_preview="进入到策略配置页面，勾选落地加密，开启加解密类型，保存并推送策略。",
            text="进入到策略配置页面，勾选落地加密，开启加解密类型，保存并推送策略。",
            keywords=["透明加解密", "策略配置", "落地加密"],
        )
        generic = MagicMock(
            heading="文件解密流程",
            heading_path="流程管理 / 文件解密流程",
            text_preview="提交解密申请后，审批通过可本地解密成明文。",
            text="提交解密申请后，审批通过可本地解密成明文。",
            keywords=["解密", "流程"],
        )
        terms = tools.terms("落地解密在哪里配置")

        policy_score, _ = tools._score_section("落地解密在哪里配置", policy, terms)
        generic_score, _ = tools._score_section("落地解密在哪里配置", generic, terms)

        self.assertGreater(policy_score, generic_score)

    def test_reader_agent_prompt_includes_history_for_followup(self):
        service = SkillKnowReaderAgentService()

        messages = service._messages(
            "请基于上面的回答继续说明：共享盘怎么配置？",
            "[ev-1]\n文档：手册\n章节：策略配置\n行号：1-5\n```markdown\n进入策略配置页面。\n```",
            history_context="用户：落地解密在哪里配置？\n\n助手：在策略配置中配置落地加密。",
        )

        user_content = messages[1]["content"]
        self.assertIn("## 会话历史上下文", user_content)
        self.assertIn("落地解密在哪里配置", user_content)
        self.assertIn("## 当前用户问题", user_content)
        self.assertIn("共享盘怎么配置", user_content)
        self.assertIn("## 内部原文依据", user_content)

    def test_reader_agent_search_query_uses_user_history_only_for_followup(self):
        service = SkillKnowReaderAgentService()

        query = service._search_query(
            "继续说明共享盘配置",
            "\n\n".join(
                [
                    "用户：落地解密在哪里配置",
                    "助手：当前知识库没有找到足够依据回答该问题。\n\n问题：网关\n\n建议补充：对应产品版本、模块名称、完整操作路径、截图或原始手册章节。",
                    "用户：网关",
                ]
            ),
        )

        self.assertIn("落地解密在哪里配置", query)
        self.assertIn("网关", query)
        self.assertIn("继续说明共享盘配置", query)
        self.assertNotIn("当前知识库没有找到足够依据", query)
        self.assertNotIn("截图或原始手册章节", query)


if __name__ == "__main__":
    unittest.main()
