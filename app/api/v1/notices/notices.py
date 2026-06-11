from fastapi import APIRouter, Query

from app.controllers.notice import notice_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.notice import NoticeCreateIn, NoticeReadIn

router = APIRouter()


@router.post("/create", summary="创建全局通知", dependencies=[DependAuth])
async def create_notice(payload: NoticeCreateIn):
    user_id = CTX_USER_ID.get()
    notice, stats = await notice_controller.create_notice(creator_id=user_id, payload=payload.model_dump())
    return Success(msg="通知发送成功", data={"notice_id": notice.id, **stats})


@router.get("/list", summary="全局通知列表", dependencies=[DependAuth])
async def list_notice(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    total, rows = await notice_controller.list_notice(page=page, page_size=page_size)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/inbox", summary="我的通知收件箱", dependencies=[DependAuth])
async def inbox_notice(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    user_id = CTX_USER_ID.get()
    total, rows = await notice_controller.inbox(user_id=user_id, page=page, page_size=page_size)
    return SuccessExtra(data=rows, total=total, page=page, page_size=page_size)


@router.get("/unread_count", summary="未读通知数量", dependencies=[DependAuth])
async def unread_count_notice():
    user_id = CTX_USER_ID.get()
    count = await notice_controller.unread_count(user_id=user_id)
    return Success(data={"unread_count": count})


@router.post("/read", summary="标记通知已读", dependencies=[DependAuth])
async def read_notice(payload: NoticeReadIn):
    user_id = CTX_USER_ID.get()
    ok = await notice_controller.read_one(user_id=user_id, notice_id=payload.notice_id)
    if not ok:
        return Fail(code=404, msg="通知不存在")
    return Success(msg="已标记为已读")


@router.post("/read_all", summary="全部标记已读", dependencies=[DependAuth])
async def read_all_notice():
    user_id = CTX_USER_ID.get()
    count = await notice_controller.read_all(user_id=user_id)
    return Success(msg="已全部标记为已读", data={"updated": count})
