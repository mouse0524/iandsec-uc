from pathlib import PurePosixPath
from urllib.parse import quote, urlencode
from typing import Optional
import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.controllers.webdav import webdav_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import User
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.webdav import WebDavShareCreateIn, WebDavShareDeleteIn
from app.utils.ops_password import generate_replace_decrypt_password, generate_server_ops_password
from app.utils.request import get_client_ip

router = APIRouter(dependencies=[DependAuth])
public_router = APIRouter()
PUBLIC_SHARE_DOWNLOAD_PATH = "/public/webdav/share/download"


def _is_apple_device(request: Request) -> bool:
    user_agent = request.headers.get("user-agent", "")
    return any(token in user_agent for token in ("iPhone", "iPad", "iPod", "Macintosh"))


def _download_headers(file_path: str, upstream_headers: dict) -> dict[str, str]:
    filename = PurePosixPath(file_path).name or "download"
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def _build_public_share_download_url(code: str, sign_data: dict) -> str:
    query = urlencode({"code": code, "ts": sign_data["ts"], "sig": sign_data["sig"]})
    return f"{PUBLIC_SHARE_DOWNLOAD_PATH}?{query}"


@router.get("/list", summary="WebDAV文件列表")
async def list_webdav(path: str = Query("/", description="目录路径")):
    logger.info("[api.webdav.list] request path={}", path)
    rows = await webdav_controller.list_dir(path)
    logger.info("[api.webdav.list] response path={} count={}", path, len(rows))
    return Success(data=rows)


@router.post("/cache/clear", summary="清理WebDAV缓存")
async def clear_webdav_cache():
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).prefetch_related("roles").first()
    role_names = [role.name for role in await user.roles] if user else []
    if not user or (not user.is_superuser and "\u7ba1\u7406\u5458" not in role_names):
        raise HTTPException(status_code=403, detail="仅管理员可清理网盘缓存")
    cleared = await webdav_controller.clear_list_cache()
    return Success(msg="网盘缓存已刷新", data={"cleared": cleared})


@router.get("/download-url", summary="生成WebDAV直接下载链接")
async def download_webdav_file(request: Request, path: str = Query(..., description="文件路径")):
    logger.info("[api.webdav.download] request path={}", path)
    user_id = CTX_USER_ID.get()
    user = await User.filter(id=user_id).first()
    sign_data = await webdav_controller.build_direct_download_signature(path=path)
    await webdav_controller.record_download_log(
        download_type="direct",
        file_path=path,
        downloader_id=user_id,
        downloader_name=(user.alias or user.username) if user else "",
        source_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        referer=request.headers.get("referer", ""),
    )
    query = urlencode({"path": path, "ts": sign_data["ts"], "sig": sign_data["sig"]})
    return Success(data={"download_url": f"/api/v1/public/webdav/download?{query}"})


@router.get("/download-log/list", summary="WebDAV下载日志")
async def list_webdav_download_logs(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    file_name: str | None = Query(None, description="文件名"),
    download_type: str | None = Query(None, description="下载类型"),
):
    total, rows = await webdav_controller.list_download_logs(
        page=page,
        page_size=page_size,
        file_name=file_name,
        download_type=download_type,
    )
    logger.info(
        "[webdav.download.log.list] page={} source_ips={}",
        page,
        [item.get("source_ip") for item in rows[:5]],
    )
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)

@router.get("/preview-cache", summary="缓存WebDAV文件用于预览")
async def cache_webdav_preview_file(
    path: str = Query(..., description="文件路径"),
    fingerprint: Optional[str] = Query(None, max_length=256, description="文件指纹"),
):
    logger.info("[api.webdav.preview_cache] request path={}", path)
    data = await webdav_controller.cache_preview_file(path, cache_fingerprint=fingerprint)
    return Success(data={"preview_url": data["url_path"], "content_type": data["content_type"]})

@router.get("/ops-password", summary="获取服务器运维工具密码")
async def get_server_ops_password():
    return Success(
        data={
            "password": generate_server_ops_password(),
            "description": "密码每天变更",
        }
    )


@router.get("/replace-decrypt-password", summary="获取替换/解密工具密码")
async def get_replace_decrypt_password():
    return Success(
        data={
            "password": generate_replace_decrypt_password(),
            "description": "密码每月变更",
        }
    )


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
    download_url = await webdav_controller.get_direct_download_url(path)
    logger.info("[webdav.direct.download] redirect ip={} path={}", client_ip, path)
    return RedirectResponse(download_url, status_code=307)

@public_router.get("/preview", summary="公开预览WebDAV文件")
async def public_preview_webdav_file(
    request: Request,
    path: str = Query(..., description="文件路径"),
    ts: Optional[int] = Query(None, description="时间戳(秒)"),
    sig: Optional[str] = Query(None, description="签名"),
):
    if ts is None or not isinstance(ts, int) or ts <= 0 or not sig:
        return Fail(code=400, msg="预览链接缺少签名参数，请重新点击文件")

    client_ip = get_client_ip(request)
    await webdav_controller.verify_direct_download_signature(path=path, ts=ts, sig=sig)
    iterator, headers = await webdav_controller.download_stream(path)
    content_type = headers.get("content-type") or headers.get("Content-Type") or "application/octet-stream"
    logger.info("[webdav.direct.preview] stream ip={} path={} content_type={}", client_ip, path, content_type)
    return StreamingResponse(iterator(), media_type=content_type, headers={"Content-Disposition": "inline"})


@public_router.get("/preview-cache/{cache_key}/{filename}", summary="Read WebDAV preview cache")
async def read_webdav_preview_cache(
    cache_key: str,
    filename: str,
    ts: Optional[int] = Query(None, description="timestamp seconds"),
    sig: Optional[str] = Query(None, description="signature"),
):
    if ts is None or not isinstance(ts, int) or ts <= 0 or not sig:
        return Fail(code=400, msg="preview cache signature is required")
    if not cache_key or len(cache_key) != 24 or any(ch not in "0123456789abcdef" for ch in cache_key):
        raise HTTPException(status_code=404, detail="preview cache not found")
    safe_name = filename.replace("\\", "_").replace("/", "_")
    await webdav_controller.verify_preview_cache_signature(cache_key=cache_key, filename=safe_name, ts=ts, sig=sig)
    target_path = os.path.abspath(os.path.join(webdav_controller.PREVIEW_CACHE_DIR, cache_key, safe_name))
    cache_root = os.path.abspath(webdav_controller.PREVIEW_CACHE_DIR)
    if not target_path.startswith(cache_root + os.sep) or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="preview cache not found")
    return FileResponse(target_path, filename=None, headers={"Content-Disposition": "inline"})

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
    data["download_url"] = _build_public_share_download_url(str(data.get("code") or ""), sign_data)
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
        data.append(
            webdav_controller._share_to_dict(
                item,
                creator_name=user_map.get(item.created_by, ""),
                download_url=_build_public_share_download_url(str(item_dict.get("code") or ""), sign_data),
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
    logger.info(
        "[webdav.share.download] client_ip={} xff={} real_ip={}",
        client_ip,
        request.headers.get("x-forwarded-for", ""),
        request.headers.get("x-real-ip", ""),
    )
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

    hit_key = f"webdav:share:hit:{client_ip}:{code}"
    try:
        hit_count = await execute_redis("incr", hit_key)
        if int(hit_count) == 1:
            await execute_redis("expire", hit_key, 60)
        if int(hit_count) > 30:
            logger.warning("[webdav.share.download] rate_limited ip={} code={} hit_count={}", client_ip, code, hit_count)
            return Fail(code=429, msg="请求过于频繁，请稍后重试")
    except Exception as exc:
        logger.warning("[webdav.share.download] rate_limit_error ip={} code={} error={}", client_ip, code, str(exc))

    share = await webdav_controller.get_share(code)
    creator = await User.filter(id=share.created_by).first()
    await webdav_controller.record_download_log(
        download_type="share",
        file_path=share.file_path,
        share_code=code,
        downloader_id=share.created_by,
        downloader_name=(creator.alias or creator.username) if creator else "",
        source_ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        referer=request.headers.get("referer", ""),
    )
    if _is_apple_device(request):
        iterator, headers = await webdav_controller.download_stream(share.file_path)
        content_type = headers.get("content-type") or headers.get("Content-Type") or "application/octet-stream"
        logger.info("[webdav.share.download] stream ip={} code={} file_path={}", client_ip, code, share.file_path)
        return StreamingResponse(
            iterator(),
            media_type=content_type,
            headers=_download_headers(share.file_path, headers),
        )

    download_url = await webdav_controller.get_direct_download_url(share.file_path)
    logger.info("[webdav.share.download] redirect ip={} code={} file_path={}", client_ip, code, share.file_path)
    return RedirectResponse(download_url, status_code=307)
