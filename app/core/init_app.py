import shutil

from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from tortoise.expressions import Q

from app.api import api_router
from app.controllers.api import api_controller
from app.controllers.user import UserCreate, user_controller
from app.core.exceptions import (
    DoesNotExist,
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.log import logger
from app.models.admin import Api, Menu, Role
from app.schemas.menus import MenuType
from app.settings.config import settings

from .middlewares import BackGroundTaskMiddleware, HttpAuditLogMiddleware


def make_middlewares():
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(BackGroundTaskMiddleware),
        Middleware(
            HttpAuditLogMiddleware,
            methods=["GET", "POST", "PUT", "DELETE"],
            exclude_paths=[
                "/api/v1/base/access_token",
                "/api/v1/base/wx_login",
                "/docs",
                "/openapi.json",
            ],
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)


async def init_superuser():
    user = await user_controller.model.exists()
    if not user:
        await user_controller.create_user(
            UserCreate(
                username="admin",
                email="admin@admin.com",
                password="123456",
                is_active=True,
                is_superuser=True,
            )
        )


async def init_menus():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=6,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        # await Menu.create(
        #     menu_type=MenuType.MENU,
        #     name="一级菜单",
        #     path="/top-menu",
        #     order=2,
        #     parent_id=0,
        #     icon="material-symbols:featured-play-list-outline",
        #     is_hidden=False,
        #     component="/top-menu",
        #     keepalive=False,
        #     redirect="",
        # )
    # 检查待办事项菜单是否存在
    todo_menu = await Menu.filter(name="待办事项").first()
    if not todo_menu:
        # 添加待办事项菜单
        todo_parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="待办事项",
            path="/todo",
            order=3,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/todo/dashboard",
        )

        todo_children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="四象限待办",
                path="quadrant",
                order=1,
                parent_id=todo_parent_menu.id,
                icon="icon-park-outline:grid-four",
                is_hidden=False,
                component="/todo/TodoQuadrant",
                keepalive=True,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="待办统计",
                path="history",
                order=2,
                parent_id=todo_parent_menu.id,
                icon="icon-park-outline:chart-line",
                is_hidden=False,
                component="/todo/TodoHistory",
                keepalive=True,
            ),
        ]
        await Menu.bulk_create(todo_children_menu)

    # 一期任务体系升级：任务列表页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        task_menu = await Menu.filter(name="任务", parent_id=todo_parent_menu.id).first()
        if not task_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="任务",
                path="tasks",
                order=0,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:task-outline",
                is_hidden=False,
                component="/todo/TaskList",
                keepalive=True,
            )

    # 二期日历排程：日历页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        schedule_menu = await Menu.filter(name="日历", parent_id=todo_parent_menu.id).first()
        if not schedule_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="日历",
                path="schedule",
                order=1,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:calendar-month-outline",
                is_hidden=False,
                component="/todo/Schedule",
                keepalive=True,
            )

    # 三期习惯打卡：习惯页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        habit_menu = await Menu.filter(name="习惯", parent_id=todo_parent_menu.id).first()
        if not habit_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="习惯",
                path="habit",
                order=2,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:sync-outline",
                is_hidden=False,
                component="/todo/Habit",
                keepalive=True,
            )

    # 三期计划目标：计划页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        goal_menu = await Menu.filter(name="计划", parent_id=todo_parent_menu.id).first()
        if not goal_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="计划",
                path="goal",
                order=3,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:flag-outline",
                is_hidden=False,
                component="/todo/Goal",
                keepalive=True,
            )

    # 四期回顾总结：回顾页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        review_menu = await Menu.filter(name="回顾总结", parent_id=todo_parent_menu.id).first()
        if not review_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="回顾总结",
                path="review",
                order=4,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:rate-review-outline",
                is_hidden=False,
                component="/todo/Review",
                keepalive=True,
            )

    # 四期今日概览：今日页菜单 + 把待办事项父菜单默认页从四象限切到今日概览。
    # 独立于上面的判断，保证已经部署过的环境重启后也能自动补上；redirect 的更新对已经存在的
    # 父菜单记录也生效，不只是全新建库时走 Step 1 的初始值。
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        dashboard_menu = await Menu.filter(name="今日", parent_id=todo_parent_menu.id).first()
        if not dashboard_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="今日",
                path="dashboard",
                order=-1,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:today-outline",
                is_hidden=False,
                component="/todo/Dashboard",
                keepalive=True,
            )
        if todo_parent_menu.redirect != "/todo/dashboard":
            todo_parent_menu.redirect = "/todo/dashboard"
            await todo_parent_menu.save()


async def init_apis():
    # refresh_api() is idempotent (upserts current routes, drops stale ones), so it must
    # run on every startup — otherwise newly added protected routes on an already-deployed
    # database never get registered until the Api table is manually cleared.
    await api_controller.refresh_api()


async def init_db():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()
    try:
        await command.migrate()
    except AttributeError:
        logger.warning("unable to retrieve model history from database, model history will be created from scratch")
        shutil.rmtree("migrations")
        await command.init_db(safe=True)

    await command.upgrade(run_in_transaction=True)


async def init_roles():
    roles = await Role.exists()
    if not roles:
        admin_role = await Role.create(
            name="管理员",
            desc="管理员角色",
        )
        user_role = await Role.create(
            name="普通用户",
            desc="普通用户角色",
        )

        # 分配所有API给管理员角色
        all_apis = await Api.all()
        await admin_role.apis.add(*all_apis)
        # 分配所有菜单给管理员和普通用户
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await user_role.menus.add(*all_menus)

        # 为普通用户分配基本API
        basic_apis = await Api.filter(Q(method__in=["GET"]) | Q(tags="基础模块"))
        await user_role.apis.add(*basic_apis)


async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await init_roles()
