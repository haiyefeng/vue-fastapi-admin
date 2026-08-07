from typing import List, Optional

from app.controllers.category import category_controller
from app.core.crud import CRUDBase
from app.models.todo import Category, Project, TodoItem
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectController(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self):
        super().__init__(model=Project)

    async def get_projects_for_user(self, user_id: int) -> List[Project]:
        return await Project.filter(user_id=user_id).order_by("name")

    async def create_project(self, obj_in: ProjectCreate, user_id: int) -> Project:
        category_id = await self._resolve_category(user_id, obj_in.category_id, obj_in.category_name)
        return await Project.create(
            user_id=user_id,
            name=obj_in.name,
            type=obj_in.type,
            category_id=category_id,
            color_hex=obj_in.color_hex,
        )

    async def update_project(self, project_id: int, obj_in: ProjectUpdate, user_id: int) -> Optional[Project]:
        project = await Project.filter(id=project_id, user_id=user_id).first()
        if not project:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id", "category_id", "category_name"})
        if "category_id" in obj_in.model_fields_set or "category_name" in obj_in.model_fields_set:
            update_data["category_id"] = await self._resolve_category(user_id, obj_in.category_id, obj_in.category_name)

        await project.update_from_dict(update_data).save()
        return project

    async def delete_project(self, project_id: int, user_id: int) -> bool:
        """删除项目不级联删任务，任务的 project_id 显式置空退回收件箱"""
        project = await Project.filter(id=project_id, user_id=user_id).first()
        if not project:
            return False
        await TodoItem.filter(project_id=project_id).update(project_id=None)
        await project.delete()
        return True

    async def to_out_dict(self, project: Project) -> dict:
        data = await project.to_dict()
        category_name = None
        if project.category_id:
            category = await project.category
            category_name = category.name if category else None
        data["category_name"] = category_name
        return data

    async def _resolve_category(
        self, user_id: int, category_id: Optional[int], category_name: Optional[str]
    ) -> Optional[int]:
        if category_id is not None:
            # Verify the category belongs to the current user or is system-predefined
            from tortoise.expressions import Q

            category = await Category.filter(
                Q(id=category_id, user_id=user_id) | Q(id=category_id, user_id__isnull=True)
            ).first()
            if category:
                return category_id
            # Category doesn't belong to user and isn't system-predefined, fall back to category_name
        if category_name:
            category = await category_controller.get_or_create(user_id, category_name)
            return category.id
        return None


project_controller = ProjectController()
