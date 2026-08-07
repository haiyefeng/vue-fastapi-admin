from typing import Optional

from pydantic import BaseModel, Field

from app.models.todo import ProjectType


class ProjectCreate(BaseModel):
    name: str = Field(..., description="项目/清单名称")
    type: ProjectType = Field(ProjectType.PROJECT, description="类型（项目或清单）")
    category_id: Optional[int] = Field(None, description="已有分类ID")
    category_name: Optional[str] = Field(None, description="新分类名称，与 category_id 二选一")
    color_hex: Optional[str] = Field(
        None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$", description="颜色代码，如 #1890FF"
    )


class ProjectUpdate(BaseModel):
    id: int = Field(..., description="项目ID")
    name: Optional[str] = None
    type: Optional[ProjectType] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    color_hex: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_archived: Optional[bool] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    type: ProjectType
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: bool

    class Config:
        from_attributes = True
