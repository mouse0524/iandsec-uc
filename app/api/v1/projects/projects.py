from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.controllers.project import project_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User
from app.schemas.base import Success, SuccessExtra
from app.schemas.projects import (
    ProjectActivityCreateIn,
    ProjectActivityUpdateIn,
    ProjectAssignIn,
    ProjectBatchUpdateIn,
    ProjectCreateIn,
    ProjectStatusIn,
    ProjectUpdateIn,
)

router = APIRouter()


async def _get_current_user() -> User:
    user = await User.filter(id=CTX_USER_ID.get()).first()
    if not user:
        raise HTTPException(status_code=401, detail="当前用户不存在")
    return user


async def _require_project_manager() -> User:
    user = await _get_current_user()
    role_names = [role.name for role in await user.roles]
    await project_controller.require_manager(user, role_names)
    return user


async def _can_view_all_projects(user: User) -> bool:
    return project_controller.can_view_all(user, [role.name for role in await user.roles])


async def _ensure_project_visible(user: User, project_id: int) -> None:
    if await _can_view_all_projects(user):
        return
    if not await project_controller.visible_projects_for_user(user.id, project_id=project_id):
        raise HTTPException(status_code=403, detail="无权访问该项目")


async def _ensure_projects_visible(user: User, project_ids: list[int]) -> None:
    if await _can_view_all_projects(user):
        return
    visible_ids = {item.id for item in await project_controller.visible_projects_for_user(user.id)}
    if any(project_id not in visible_ids for project_id in project_ids):
        raise HTTPException(status_code=403, detail="无权访问该项目")


@router.get("/list", summary="项目列表", dependencies=[DependAuth])
async def list_projects(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    project_name: str | None = Query(None, description="项目名称"),
    region: str | None = Query(None, description="区域"),
    agent_id: int | None = Query(None, description="所属代理商ID"),
    status: str | None = Query(None, description="项目状态"),
    assignee_id: int | None = Query(None, description="负责人ID"),
):
    user = await _require_project_manager()
    if not await _can_view_all_projects(user):
        assignee_id = user.id
    filters = {
        "project_name": project_name,
        "region": region,
        "agent_id": agent_id,
        "status": status,
        "assignee_id": assignee_id,
    }
    total, rows = await project_controller.list_projects(
        page=page,
        page_size=page_size,
        filters=filters,
    )
    return SuccessExtra(
        data=rows,
        total=total,
        page=page,
        page_size=page_size,
        summary=await project_controller.project_summary(filters),
    )


@router.get("/get", summary="项目详情", dependencies=[DependAuth])
async def get_project(project_id: int = Query(..., description="项目ID")):
    user = await _require_project_manager()
    await _ensure_project_visible(user, project_id)
    return Success(data=await project_controller.get_project(project_id))


@router.post("/upload", summary="上传项目附件", dependencies=[DependAuth])
async def upload_project_attachment(file: UploadFile = File(...)):
    user = await _require_project_manager()
    attachment = await project_controller.upload_attachment(uploader_id=user.id, file=file)
    return Success(data=await attachment.to_dict())


@router.post("/import", summary="批量导入项目", dependencies=[DependAuth])
async def import_projects(file: UploadFile = File(...)):
    user = await _require_project_manager()
    return Success(data=await project_controller.import_projects(user_id=user.id, file=file))


@router.get("/attachment/download", summary="下载项目附件", dependencies=[DependAuth])
async def download_project_attachment(attachment_id: int = Query(..., description="附件ID")):
    user = await _require_project_manager()
    data = await project_controller.get_attachment_download(attachment_id=attachment_id)
    await _ensure_project_visible(user, data["project_id"])
    return FileResponse(data["abs_path"], media_type=data["media_type"], filename=None, headers=data["headers"])


@router.post("/create", summary="创建项目", dependencies=[DependAuth])
async def create_project(payload: ProjectCreateIn):
    user = await _require_project_manager()
    project = await project_controller.create_project(user_id=user.id, payload=payload.model_dump())
    return Success(data=await project_controller.get_project(project.id))


@router.post("/update", summary="更新项目", dependencies=[DependAuth])
async def update_project(payload: ProjectUpdateIn):
    user = await _require_project_manager()
    await _ensure_project_visible(user, payload.project_id)
    data = payload.model_dump(exclude={"project_id"})
    if "attachment_ids" not in payload.model_fields_set:
        data.pop("attachment_ids", None)
    project = await project_controller.update_project(project_id=payload.project_id, user_id=user.id, payload=data)
    return Success(data=await project_controller.get_project(project.id))


@router.post("/status", summary="流转项目状态", dependencies=[DependAuth])
async def set_project_status(payload: ProjectStatusIn):
    user = await _require_project_manager()
    await _ensure_project_visible(user, payload.project_id)
    project = await project_controller.set_status(project_id=payload.project_id, status=payload.status)
    return Success(data=await project_controller.get_project(project.id))


@router.post("/assign", summary="指派项目负责人", dependencies=[DependAuth])
async def assign_project(payload: ProjectAssignIn):
    user = await _require_project_manager()
    await _ensure_project_visible(user, payload.project_id)
    project = await project_controller.assign(
        project_id=payload.project_id,
        user_id=user.id,
        assignee_id=payload.assignee_id,
    )
    return Success(data=await project_controller.get_project(project.id))


@router.post("/batch-update", summary="批量修改项目", dependencies=[DependAuth])
async def batch_update_projects(payload: ProjectBatchUpdateIn):
    user = await _require_project_manager()
    await _ensure_projects_visible(user, payload.project_ids)
    count = await project_controller.batch_update_projects(
        project_ids=payload.project_ids,
        user_id=user.id,
        payload=payload.model_dump(exclude={"project_ids"}, exclude_unset=True),
    )
    return Success(data={"count": count})


@router.get("/activity/list", summary="项目活动列表", dependencies=[DependAuth])
async def list_project_activities(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    project_id: int | None = Query(None, description="项目ID"),
    activity_type: str | None = Query(None, description="活动类型"),
    status: str | None = Query(None, description="活动状态"),
):
    user = await _require_project_manager()
    filters = {"project_id": project_id, "activity_type": activity_type, "status": status}
    if not await _can_view_all_projects(user):
        filters["project_ids"] = [
            item.id for item in await project_controller.visible_projects_for_user(user.id, project_id=project_id)
        ]
    total, rows = await project_controller.list_activities(
        page=page,
        page_size=page_size,
        filters=filters,
    )
    return SuccessExtra(
        data=rows,
        total=total,
        page=page,
        page_size=page_size,
        summary=await project_controller.activity_summary(filters),
    )


@router.post("/activity/create", summary="创建项目活动", dependencies=[DependAuth])
async def create_project_activity(payload: ProjectActivityCreateIn):
    user = await _require_project_manager()
    await _ensure_project_visible(user, payload.project_id)
    activity = await project_controller.save_activity(user_id=user.id, payload=payload.model_dump())
    return Success(data=await project_controller._activity_row(activity))


@router.post("/activity/update", summary="更新项目活动", dependencies=[DependAuth])
async def update_project_activity(payload: ProjectActivityUpdateIn):
    user = await _require_project_manager()
    old_activity = await project_controller.get_activity(payload.activity_id)
    await _ensure_project_visible(user, old_activity.project_id)
    data = payload.model_dump(exclude={"activity_id"})
    await _ensure_project_visible(user, data["project_id"])
    activity = await project_controller.save_activity(
        user_id=user.id,
        payload=data,
        activity_id=payload.activity_id,
    )
    return Success(data=await project_controller._activity_row(activity))
