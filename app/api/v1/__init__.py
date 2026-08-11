from fastapi import APIRouter

from app.core.dependency import DependPermission

from .apis import apis_router
from .auditlog import auditlog_router
from .base import base_router
from .category import category_router
from .depts import depts_router
from .goal import goal_router
from .habit import habit_router
from .menus import menus_router
from .project import project_router
from .roles import roles_router
from .subtask import subtask_router
from .timeblock import timeblock_router
from .todos import todos_router
from .users import users_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(todos_router, prefix="/todo", dependencies=[DependPermission])
v1_router.include_router(category_router, prefix="/category", dependencies=[DependPermission])
v1_router.include_router(goal_router, prefix="/goal", dependencies=[DependPermission])
v1_router.include_router(project_router, prefix="/project", dependencies=[DependPermission])
v1_router.include_router(subtask_router, prefix="/subtask", dependencies=[DependPermission])
v1_router.include_router(timeblock_router, prefix="/timeblock", dependencies=[DependPermission])
v1_router.include_router(habit_router, prefix="/habit", dependencies=[DependPermission])
