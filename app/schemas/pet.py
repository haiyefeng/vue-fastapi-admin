from typing import Optional

from pydantic import BaseModel, Field


class PetUpdate(BaseModel):
    active_cat_id: Optional[str] = Field(None, description="切换到的猫，必须已解锁")
    pet_name: Optional[str] = Field(None, description="给猫起的名字，超过 20 字会被截断")
