from fastapi import APIRouter, File, Form, Query, UploadFile

from app.log import logger
from app.controllers.captcha import captcha_controller
from app.controllers.partner import partner_controller
from app.controllers.system_setting import system_setting_controller
from app.controllers.ticket import ticket_controller
from app.models.admin import TicketAttachment
from app.schemas.base import Fail, Success
from app.schemas.tickets import TicketCreate

router = APIRouter()


@router.post("/upload", summary="游客上传工单附件")
async def upload_public_ticket_attachment(
    file: UploadFile = File(...),
    captcha_id: str = Form(...),
    captcha_code: str = Form(...),
):
    logger.info("[api.public_ticket.upload] request filename={}", file.filename)
    valid = await captcha_controller.verify_captcha(captcha_id, captcha_code, consume=False)
    if not valid:
        return Fail(code=400, msg="验证码错误或已过期")
    attachment = await ticket_controller.upload_attachment(uploader_id=0, file=file)
    await ticket_controller.remember_guest_attachment(captcha_id=captcha_id, attachment_id=attachment.id)
    logger.info("[api.public_ticket.upload] success attachment_id={}", attachment.id)
    return Success(data=await attachment.to_dict())


@router.post("/create", summary="游客提交工单")
async def create_public_ticket(payload: TicketCreate):
    logger.info(
        "[api.public_ticket.create] request email={} project_phase={} category={} title={} attachment_ids={}",
        payload.email,
        payload.project_phase,
        payload.category,
        payload.title,
        payload.attachment_ids,
    )
    pending = await partner_controller.has_pending_registration(email=payload.email, phone=payload.phone)
    if pending:
        return Fail(code=403, msg="当前账号存在待审核注册申请，暂不允许提交工单")

    valid = await captcha_controller.verify_captcha(payload.captcha_id, payload.captcha_code)
    if not valid:
        logger.warning("[api.public_ticket.create] captcha_invalid email={}", payload.email)
        return Fail(code=400, msg="验证码错误或已过期")

    config = await system_setting_controller.get_public_config()
    project_phases = config.get("ticket_project_phases") or []
    categories = config.get("ticket_categories") or []
    if project_phases and payload.project_phase not in project_phases:
        return Fail(code=400, msg="项目阶段不合法，请刷新页面后重试")
    if categories and payload.category not in categories:
        return Fail(code=400, msg="问题分类不合法，请刷新页面后重试")

    body = payload.model_dump(exclude={"captcha_id", "captcha_code"})
    await ticket_controller.validate_guest_attachment_ids(captcha_id=payload.captcha_id, attachment_ids=body.get("attachment_ids") or [])
    ticket = await ticket_controller.create_ticket(submitter_id=0, payload=body)
    await ticket_controller.consume_guest_attachment_ids(captcha_id=payload.captcha_id, attachment_ids=body.get("attachment_ids") or [])
    logger.info(
        "[api.public_ticket.create] success ticket_id={} ticket_no={} attachment_ids={}",
        ticket.id,
        ticket.ticket_no,
        payload.attachment_ids,
    )
    return Success(msg="提交成功", data=await ticket.to_dict())


@router.get("/attachments", summary="游客工单附件列表")
async def list_public_attachments(
    ids: str = Query("", description="附件ID，逗号分隔"),
    captcha_id: str = Query(..., description="验证码ID"),
):
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not id_list:
        return Success(data=[])
    await ticket_controller.validate_guest_attachment_ids(captcha_id=captcha_id, attachment_ids=id_list)
    rows = await TicketAttachment.filter(id__in=id_list, uploader_id=0).order_by("id")
    data = [
        {
            "id": item.id,
            "origin_name": item.origin_name,
            "file_size": item.file_size,
            "mime_type": item.mime_type,
        }
        for item in rows
    ]
    return Success(data=data)
