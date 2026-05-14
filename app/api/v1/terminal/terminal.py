from fastapi import APIRouter, Header, Query, Request

from app.schemas.base import Success, SuccessExtra
from app.schemas.terminal import TerminalAuthReportIn, TerminalUpgradeCheckIn, TerminalUpgradeConfigIn
from app.services.terminal_service import terminal_service
from app.utils.request import get_client_ip

router = APIRouter()
public_router = APIRouter()


@public_router.post("/auth/report", summary="终端授权信息上报")
async def report_terminal_auth(
    payload: TerminalAuthReportIn,
    request: Request,
    x_terminal_token: str | None = Header(default=None, alias="X-Terminal-Token"),
):
    data = await terminal_service.report_auth(payload, source_ip=get_client_ip(request), token=x_terminal_token)
    return Success(msg="上报成功", data=data)


@public_router.post("/upgrade/check", summary="终端升级检测")
async def check_terminal_upgrade(payload: TerminalUpgradeCheckIn):
    return Success(data=await terminal_service.check_upgrade(payload))


@router.get("/auth/list", summary="授权校验上报列表")
async def list_terminal_auth_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    company_name: str | None = Query(None, description="公司名称"),
):
    total, rows = await terminal_service.list_auth_reports(page=page, page_size=page_size, company_name=company_name)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/auth/latest", summary="最新授权校验上报")
async def latest_terminal_auth_report(company_name: str | None = Query(None, description="公司名称")):
    return Success(data=await terminal_service.latest_auth_report(company_name=company_name))


@router.get("/upgrade/config", summary="获取终端升级配置")
async def get_terminal_upgrade_config():
    return Success(data=await terminal_service.get_upgrade_config())


@router.post("/upgrade/config", summary="保存终端升级配置")
async def save_terminal_upgrade_config(payload: TerminalUpgradeConfigIn):
    return Success(msg="保存成功", data=await terminal_service.save_upgrade_config(payload))
