from typing import List

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.todo import Category


class CategoryController(CRUDBase[Category, Category, Category]):
    def __init__(self):
        super().__init__(model=Category)

    async def get_categories_for_user(self, user_id: int) -> List[Category]:
        """当前用户可见的分类：自己创建的 + 系统预设（user 为空，本期暂无预置数据）"""
        return await Category.filter(Q(user_id=user_id) | Q(user_id__isnull=True)).order_by("display_order", "name")

    async def get_or_create(self, user_id: int, name: str) -> Category:
        category = await Category.filter(user_id=user_id, name=name).first()
        if category:
            return category
        return await Category.create(user_id=user_id, name=name)


category_controller = CategoryController()
