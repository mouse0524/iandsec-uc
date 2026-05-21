from urllib.parse import urlencode
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.controllers.webdav import webdav_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import User
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.webdav import WebDavShareCreateIn, WebDavShareDeleteIn
from app.utils.http_headers import build_download_content_disposition
from app.utils.request import get_client_ip

router = APIRouter(dependencies=[DependAuth])
public_router = APIRouter()


@router.get("/list", summary="WebDAV文件列表")
async def list_webdav(path: str = Query("/", description="目录路径")):
    logger.info("[api.webdav.list] request path={}", path)
    rows = await webdav_controller.list_dir(path)
    logger.info("[api.webdav.list] response path={} count={}", path, len(rows))
    return Success(data=rows)


@router.get("/download-url", summary="生成WebDAV直接下载链接")
async def download_webdav_file(path: str = Query(..., description="文件路径")):
    logger.info("[api.webdav.download] request path={}", path)
    sign_data = await webdav_controller.build_direct_download_signature(path=path)
    query = urlencode({"path": path, "ts": sign_data["ts"], "sig": sign_data["sig"]})
    return Success(data={"download_url": f"/api/v1/public/webdav/download?{query}"})


@public_router.get("/download", summary="公开直接下载WebDAV文件")
async def public_download_webdav_file(
    request: Request,
    path: str = Query(..., description="文件路径"),
    ts: Optional[int] = Query(None, description="时间戳(秒)"),
    sig: Optional[str] = Query(None, description="签名"),
):
    if ts is None or not isinstance(ts, int) or ts <= 0 or not sig:
        return Fail(code=400, msg="下载链接缺少签名参数，请重新点击直接下载")

    client_ip = get_client_ip(request)
    await webdav_controller.verify_direct_download_signature(path=path, ts=ts, sig=sig)
    iterator, headers = await webdav_controller.download_stream(path)
    content_type = headers.get("content-type") or "application/octet-stream"
    file_name = path.rstrip("/").split("/")[-1] or "download"
    disposition = build_download_content_disposition(file_name)
    logger.info("[webdav.direct.download] success ip={} path={}", client_ip, path)
    return StreamingResponse(
        iterator(),
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )


@router.post("/share/create", summary="创建WebDAV分享")
async def create_webdav_share(payload: WebDavShareCreateIn):
    user_id = CTX_USER_ID.get()
    data = await webdav_controller.create_share(
        file_path=payload.file_path,
        file_name=payload.file_name,
        created_by=user_id,
        expire_hours=payload.expire_hours,
    )
    sign_data = await webdav_controller.build_share_signature(code=str(data.get("code") or ""))
    query = urlencode({"code": data.get("code"), "ts": sign_data["ts"], "sig": sign_data["sig"]})
    data["download_url"] = f"/api/v1/public/webdav/share/download?{query}"
    return Success(msg="分享创建成功", data=data)


@router.get("/share/list", summary="WebDAV分享记录")
async def list_webdav_shares(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    include_history: bool = Query(False, description="是否包含历史记录(已失效/已过期)"),
    file_name: str | None = Query(None, description="文件名模糊搜索"),
):
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).first()
    is_admin = bool(user and user.is_superuser)
    created_by = None if is_admin else user_id
    total, rows = await webdav_controller.list_shares(
        created_by=created_by,
        page=page,
        page_size=page_size,
        include_history=include_history,
        file_name=file_name,
    )
    user_ids = {item.created_by for item in rows}
    user_map: dict[int, str] = {}
    if user_ids:
        users = await User.filter(id__in=list(user_ids)).values("id", "alias", "username")
        user_map = {u["id"]: (u.get("alias") or u.get("username") or "") for u in users}
    data = []
    for item in rows:
        item_dict = await item.to_dict()
        sign_data = await webdav_controller.build_share_signature(code=str(item_dict.get("code") or ""))
        query = urlencode({"code": item_dict.get("code"), "ts": sign_data["ts"], "sig": sign_data["sig"]})
        data.append(
            webdav_controller._share_to_dict(
                item,
                creator_name=user_map.get(item.created_by, ""),
                download_url=f"/api/v1/public/webdav/share/download?{query}",
                data=item_dict,
            )
        )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/share/delete", summary="删除WebDAV分享记录")
async def delete_webdav_share(payload: WebDavShareDeleteIn):
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).first()
    is_admin = bool(user and user.is_superuser)
    await webdav_controller.delete_share(payload.id, None if is_admin else user_id)
    return Success(msg="删除成功")


@public_router.get("/share/download", summary="公开下载WebDAV分享文件")
async def webdav_share_download(
    request: Request,
    code: str = Query(..., description="分享码"),
    ts: Optional[int] = Query(None, description="时间戳(秒)"),
    sig: Optional[str] = Query(None, description="签名"),
):
    if ts is None or not isinstance(ts, int) or ts <= 0 or not sig:
        return Fail(code=400, msg="分享链接缺少签名参数，请重新复制最新下载链接")

    client_ip = get_client_ip(request)
    fail_key = f"webdav:share:fail:{client_ip}:{code}"
    blocked_key = f"webdav:share:blocked:{client_ip}:{code}"
    try:
        blocked = await execute_redis("get", blocked_key)
        if blocked:
            logger.warning("[webdav.share.download] blocked ip={} code={}", client_ip, code)
            return Fail(code=429, msg="请求过于频繁，请稍后重试")
    except Exception as exc:
        logger.warning("[webdav.share.download] block_check_failed ip={} code={} error={}", client_ip, code, str(exc))

    try:
        await webdav_controller.verify_share_signature(code=code, ts=ts, sig=sig)
    except Exception as exc:
        try:
            fail_count = await execute_redis("incr", fail_key)
            if int(fail_count) == 1:
                await execute_redis("expire", fail_key, 600)
            if int(fail_count) >= 8:
                await execute_redis("setex", blocked_key, 900, 1)
            logger.warning(
                "[webdav.share.download] sign_failed ip={} code={} fail_count={} error={}",
                client_ip,
                code,
                fail_count,
                str(exc),
            )
        except Exception as counter_exc:
            logger.warning("[webdav.share.download] fail_counter_error ip={} code={} error={}", client_ip, code, str(counter_exc))
        raise

    share = await webdav_controller.get_share(code)
    iterator, headers = await webdav_controller.download_stream(share.file_path)
    content_type = headers.get("content-type") or "application/octet-stream"
    disposition = build_download_content_disposition(share.file_name)
    logger.info("[webdav.share.download] success ip={} code={} file_path={}", client_ip, code, share.file_path)
    return StreamingResponse(
        iterator(),
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )
