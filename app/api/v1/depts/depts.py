import json
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.controllers.dept import dept_controller
from app.core.redis_client import execute_redis
from app.schemas import Success
from app.schemas.depts import *
from app.utils.http_headers import build_download_content_disposition

router = APIRouter()


@router.get("/list", summary="查看部门列表")
async def list_dept(
    name: str = Query(None, description="部门名称"),
):
    if not name:
        try:
            cached = await execute_redis("get", dept_controller.DEPT_DICT_CACHE_KEY)
            if cached:
                return Success(data=json.loads(cached))
        except Exception:
            pass

    dept_tree = await dept_controller.get_dept_tree(name)
    if not name:
        try:
            await execute_redis("setex", dept_controller.DEPT_DICT_CACHE_KEY, 600, json.dumps(dept_tree, ensure_ascii=False))
        except Exception:
            pass
    return Success(data=dept_tree)


@router.get("/get", summary="查看部门")
async def get_dept(
    id: int = Query(..., description="部门ID"),
):
    dept_obj = await dept_controller.get(id=id)
    data = await dept_obj.to_dict()
    return Success(data=data)


@router.get("/export", summary="导出部门")
async def export_dept():
    data = await dept_controller.export_depts()
    filename = f"depts_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": build_download_content_disposition(filename)},
    )


@router.post("/import", summary="导入部门")
async def import_dept(file: UploadFile = File(...)):
    return Success(data=await dept_controller.import_depts(file))


@router.post("/create", summary="创建部门")
async def create_dept(
    dept_in: DeptCreate,
):
    await dept_controller.create_dept(obj_in=dept_in)
    return Success(msg="Created Successfully")


@router.post("/update", summary="更新部门")
async def update_dept(
    dept_in: DeptUpdate,
):
    await dept_controller.update_dept(obj_in=dept_in)
    return Success(msg="Update Successfully")


@router.delete("/delete", summary="删除部门")
async def delete_dept(
    dept_id: int = Query(..., description="部门ID"),
):
    await dept_controller.delete_dept(dept_id=dept_id)
    return Success(msg="Deleted Success")
