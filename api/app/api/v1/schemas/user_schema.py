from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class UserBase(BaseModel):
    userid: str
    email: EmailStr


class UserCreate(UserBase):
    password: str = None
    phone: Optional[str] = None
    name: Optional[str] = ""
    avatar_url: Optional[str] = ""
    # sign_up_from: Optional[str] = "stocking"
    # uuid: Optional[str] = ""
    platform: Optional[str] = ""


class UserPatch(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    push_on: Optional[bool] = None


class PushTokenPatch(BaseModel):
    push_token: str
    platform: str


class RequestLogin(BaseModel):
    userid: str
    password: str


class ResponseUser(InitVarModel):
    id: str
    name: str
    avatar_url: Optional[str]
    phone: Optional[str]
    sign_in_count: int
    last_sign_in_at: Optional[int]
    last_sign_in_ip: Optional[str]
    access_token: Optional[str]
    refresh_token: Optional[str]
    sign_up_from: str
    created_at: int
    updated_at: int


    _timestamp_fields = {'last_sign_in_at', 'updated_at', 'created_at'}
    # 다른 필드의 기본값
    _default_values = {
        'avatar_url': "",
        'phone': "",
        'last_sign_in_ip': ""
    }

    # @field_validator('created_at', 'updated_at', 'last_sign_in_at', mode='before')
    # @classmethod
    # def datetime_to_timestamp(cls, value):
    #     """datetime 객체를 Unix 타임스탬프(초)로 변환"""
    #     if isinstance(value, datetime):
    #         return int(value.timestamp())
    #     return value


class UserListItem(InitVarModel):
    id: str
    name: str
    avatar_url: Optional[str]
    phone: Optional[str]
    sign_in_count: int
    last_sign_in_at: Optional[int]
    last_sign_in_ip: Optional[str]
    updated_at: Optional[int]

    _timestamp_fields = {'last_sign_in_at', 'updated_at'}
    # 다른 필드의 기본값
    _default_values = {
        'avatar_url': "",
        'phone': "",
        'last_sign_in_ip': ""
    }


# 페이징된 사용자 응답 스키마 - 공통 응답 활용
class UserListResponse(PagedResponse[UserListItem]):
    """페이징된 사용자 목록 응답"""
    pass
