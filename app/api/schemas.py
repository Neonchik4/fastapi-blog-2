from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, computed_field


class BaseModelConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BlogCreateSchemaBase(BaseModelConfig):
    title: str
    content: str
    short_description: str
    tags: List[str] = []


class BlogCreateSchemaAdd(BlogCreateSchemaBase):
    author: int


class UserBase(BaseModelConfig):
    id: int
    first_name: str
    last_name: str


class TagResponse(BaseModelConfig):
    id: int
    name: str


class BlogFullResponse(BaseModelConfig):
    id: int
    author: int
    title: str
    content: str
    short_description: str
    created_at: datetime
    status: str
    tags: List[TagResponse]
    user: UserBase = Field(exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author_id(self) -> int | None:
        return self.user.id if self.user else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def author_name(self) -> str | None:
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        return None


class BlogNotFind(BaseModel):
    message: str
    status: str
