from pydantic import BaseModel

from app.models.todo import CategoryType


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: str | None = None
    type: CategoryType
    display_order: int
    is_archived: bool

    class Config:
        from_attributes = True
