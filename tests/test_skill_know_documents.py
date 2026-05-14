import asyncio
import base64
import sys
import types
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.services.skill_know.chroma_store import SkillKnowChromaStore
from app.services.skill_know.document_service import SkillKnowDocumentService
from app.services.skill_know.retriever import SkillKnowRetriever
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

    def test_chroma_client_uses_existing_telemetry_impl_with_telemetry_disabled(self):
        store = SkillKnowChromaStore()
        chromadb_module = types.SimpleNamespace(PersistentClient=MagicMock(return_value=MagicMock()))
        class FakeSettings:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        with (
            patch.dict(sys.modules, {"chromadb": chromadb_module, "chromadb.config": types.SimpleNamespace(Settings=FakeSettings)}),
            patch("app.services.skill_know.chroma_store.os.makedirs"),
        ):
            store._client()

        settings = chromadb_module.PersistentClient.call_args.kwargs["settings"]
        self.assertFalse(settings.anonymized_telemetry)
        self.assertEqual(settings.chroma_product_telemetry_impl, "chromadb.telemetry.product.posthog.Posthog")
        self.assertNotIn(".null.", settings.chroma_product_telemetry_impl)

    def test_retriever_expands_hit_with_neighbor_chunks(self):
        retriever = SkillKnowRetriever()
        before = MagicMock(document_id=1, chunk_index=0, content="上文：登录失败时")
        after = MagicMock(document_id=1, chunk_index=2, content="下文：再联系管理员")

        class AwaitableRows:
            def __await__(self):
                async def rows():
                    return [before, after]

                return rows().__await__()

        async def run():
            with patch("app.services.skill_know.retriever.SkillKnowDocumentChunk.filter", return_value=AwaitableRows()) as chunk_filter:
                result = await retriever._expand_with_neighbor_context(
                    [
                        {
                            "document_id": 1,
                            "chunk_id": 10,
                            "chunk_uri": "doc#chunk-1",
                            "content": "命中：请重新获取验证码",
                            "metadata": {"chunk_index": 1},
                        }
                    ]
                )
            return result, chunk_filter

        result, chunk_filter = asyncio.run(run())

        self.assertIn("[上一片段]", result[0]["content"])
        self.assertIn("[命中片段]", result[0]["content"])
        self.assertIn("[下一片段]", result[0]["content"])
        self.assertTrue(result[0]["metadata"]["context_expanded"])
        chunk_filter.assert_called_once_with(document_id=1, chunk_index__in=[0, 2])


if __name__ == "__main__":
    unittest.main()
