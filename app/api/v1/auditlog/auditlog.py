import csv
import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.models.admin import AuditLog
from app.schemas import Fail, Success, SuccessExtra
from app.schemas.apis import *
from app.utils.http_headers import build_download_content_disposition

router = APIRouter()


@router.get("/list", summary="查看操作日志")
async def get_audit_log_list(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    username: str = Query("", description="操作人名称"),
    module: str = Query("", description="功能模块"),
    method: str = Query("", description="请求方法"),
    summary: str = Query("", description="接口描述"),
    path: str = Query("", description="请求路径"),
    status: int = Query(None, description="状态码"),
    start_time: datetime = Query("", description="开始时间"),
    end_time: datetime = Query("", description="结束时间"),
    include_archived: bool = Query(False, description="是否包含已归档日志"),
):
    q = Q()
    if not include_archived:
        q &= Q(is_archived=False)
    if username:
        q &= Q(username__icontains=username)
    if module:
        q &= Q(module__icontains=module)
    if method:
        q &= Q(method__icontains=method)
    if summary:
        q &= Q(summary__icontains=summary)
    if path:
        q &= Q(path__icontains=path)
    if status:
        q &= Q(status=status)
    if start_time and end_time:
        q &= Q(created_at__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_at__gte=start_time)
    elif end_time:
        q &= Q(created_at__lte=end_time)

    audit_log_objs = await AuditLog.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    total = await AuditLog.filter(q).count()
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/archive", summary="归档审计日志")
async def archive_audit_logs(
    before_time: datetime | None = Query(None, description="归档该时间之前的日志"),
):
    q = Q(is_archived=False)
    if before_time:
        q &= Q(created_at__lte=before_time)
    count = await AuditLog.filter(q).update(is_archived=True)
    return Success(msg="归档成功", data={"archived": count})


@router.post("/clear", summary="清空审计日志")
async def clear_audit_logs(confirm: bool = Query(False, description="确认清空")):
    if not confirm:
        return Fail(msg="请传入 confirm=true 确认清空", data={"cleared": 0})
    count = await AuditLog.all().count()
    await AuditLog.all().delete()
    return Success(msg="清空成功", data={"cleared": count})


@router.get("/export", summary="导出审计日志ZIP")
async def export_audit_logs(
    include_archived: bool = Query(True, description="是否包含已归档日志"),
    username: str = Query("", description="操作人名称"),
    module: str = Query("", description="功能模块"),
    method: str = Query("", description="请求方法"),
    summary: str = Query("", description="接口描述"),
    path: str = Query("", description="请求路径"),
    status: int = Query(None, description="状态码"),
    start_time: datetime = Query("", description="开始时间"),
    end_time: datetime = Query("", description="结束时间"),
):
    if not start_time and not end_time:
        return Fail(msg="请选择开始时间或结束时间后再导出审计日志")
    q = Q()
    if not include_archived:
        q &= Q(is_archived=False)
    if username:
        q &= Q(username__icontains=username)
    if module:
        q &= Q(module__icontains=module)
    if method:
        q &= Q(method__icontains=method)
    if summary:
        q &= Q(summary__icontains=summary)
    if path:
        q &= Q(path__icontains=path)
    if status:
        q &= Q(status=status)
    if start_time and end_time:
        q &= Q(created_at__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_at__gte=start_time)
    elif end_time:
        q &= Q(created_at__lte=end_time)
    rows = await AuditLog.filter(q).order_by("-created_at")
    data = [await item.to_dict() for item in rows]

    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    csv_buffer = io.StringIO()
    fieldnames = [
        "id",
        "user_id",
        "username",
        "module",
        "summary",
        "method",
        "path",
        "status",
        "response_time",
        "request_args",
        "response_body",
        "is_archived",
        "created_at",
        "updated_at",
    ]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in data:
        output = {key: row.get(key) for key in fieldnames}
        output["request_args"] = json.dumps(output.get("request_args"), ensure_ascii=False)
        output["response_body"] = json.dumps(output.get("response_body"), ensure_ascii=False)
        writer.writerow(output)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("audit_logs.json", json_text.encode("utf-8"))
        archive.writestr("audit_logs.csv", csv_buffer.getvalue().encode("utf-8-sig"))
    zip_buffer.seek(0)

    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": build_download_content_disposition(filename)},
    )
