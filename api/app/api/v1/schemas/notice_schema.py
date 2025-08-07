from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel
from app.api.v1.schemas.user_schema import UserListItem
from app.db.models import Notice


class NoticeBase(BaseModel):
    title: str = Field(..., description="공지사항 제목")
    content: str = Field(..., description="공지사항 내용")
    is_active: bool = Field(True, description="활성화 여부")


class NoticeCreate(NoticeBase):
    pass


class NoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, description="공지사항 제목")
    content: Optional[str] = Field(None, description="공지사항 내용")
    is_active: Optional[bool] = Field(None, description="활성화 여부")


class NoticeResponse(InitVarModel):
    id: str
    title: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserListItem] = None

    class Config:
        from_attributes = True


class NoticeListItem(BaseModel):
    id: str
    title: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserListItem] = None

    class Config:
        from_attributes = True


class NoticeListResponse(PagedResponse[NoticeListItem]):
    pass


def notice_to_response(notice: Notice) -> NoticeResponse:
    """공지사항 모델을 응답 스키마로 변환"""
    creator = None
    if notice.creator:
        creator = UserListItem(
            id=notice.creator.id,
            userid=notice.creator.userid,
            name=notice.creator.name,
            email=notice.creator.email,
            avatar_url=notice.creator.avatar_url
        )

    return NoticeResponse(
        id=notice.id,
        title=notice.title,
        content=notice.content,
        is_active=notice.is_active,
        created_at=notice.created_at,
        updated_at=notice.updated_at,
        creator=creator
    )