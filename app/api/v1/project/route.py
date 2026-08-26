import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.category import category_controller
from app.controllers.project import project_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.category import CategoryOut
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户的项目/清单列表")
async def list_projects(current_user: User = Depends(AuthControl.is_authed)):
    projects = await project_controller.get_projects_for_user(current_user.id)
    result = [ProjectOut(**(await project_controller.to_out_dict(p))).model_dump() for p in projects]
    return Success(data=result)


@router.get("/bootstrap", summary="项目页首屏聚合（项目/清单 + 分类）")
async def bootstrap_projects(current_user: User = Depends(AuthControl.is_authed)):
    """项目列表与分类列表一次返回；分类复用 category 模块，不重复实现一份"""
    projects = await project_controller.get_projects_for_user(current_user.id)
    categories = await category_controller.get_categories_for_user(current_user.id)
    return Success(
        data={
            "list": [ProjectOut(**(await project_controller.to_out_dict(p))).model_dump() for p in projects],
            "categories": [CategoryOut(**(await c.to_dict())).model_dump() for c in categories],
        }
    )


@router.post("/create", summary="创建项目/清单")
async def create_project(project_in: ProjectCreate, current_user: User = Depends(AuthControl.is_authed)):
    project = await project_controller.create_project(project_in, current_user.id)
    data = await project_controller.to_out_dict(project)
    return Success(data=ProjectOut(**data).model_dump())


@router.post("/update", summary="更新项目/清单")
async def update_project(project_in: ProjectUpdate, current_user: User = Depends(AuthControl.is_authed)):
    project = await project_controller.update_project(project_in.id, project_in, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = await project_controller.to_out_dict(project)
    return Success(data=ProjectOut(**data).model_dump())


@router.delete("/delete", summary="删除项目/清单")
async def delete_project(
    project_id: int = Query(..., description="项目ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await project_controller.delete_project(project_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return Success(msg="删除成功")
