import asyncio
from unittest.mock import AsyncMock, patch

from app.services.system_monitor_service import SystemMonitorService


def test_skill_know_index_status_maps_health_detail():
    service = SystemMonitorService()

    async def run():
        with (
            patch("app.services.system_monitor_service.execute_redis", AsyncMock(return_value=None)),
            patch(
                "app.services.system_monitor_service.skill_know_index_health_service.detail",
                AsyncMock(
                    return_value={
                        "status": "healthy",
                        "components": {"reader_index": "ok"},
                        "reader_index": {
                            "backend": "whoosh",
                            "available": True,
                            "exists": True,
                            "doc_count": 3,
                            "document_count": 2,
                            "section_count": 3,
                        },
                    }
                ),
            ),
        ):
            return await service.skill_know_index_status()

    data = asyncio.run(run())

    assert data["status"] == "ok"
    assert data["backend"] == "whoosh"
    assert data["doc_count"] == 3
    assert data["document_count"] == 2
    assert data["components"]["reader_index"] == "ok"


def test_skill_know_index_status_reports_detail_errors():
    service = SystemMonitorService()

    async def run():
        with (
            patch("app.services.system_monitor_service.execute_redis", AsyncMock(return_value=None)),
            patch(
                "app.services.system_monitor_service.skill_know_index_health_service.detail",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            return await service.skill_know_index_status()

    data = asyncio.run(run())

    assert data["status"] == "error"
    assert "boom" in data["error"]

