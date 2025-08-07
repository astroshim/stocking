from typing import List, Optional
from pydantic import BaseModel, Field

from app.api.schemas.init_var_model import InitVarModel
from app.api.schemas.common_pagenation import PagedResponse


class RoleBase(BaseModel):
    """역할 기본 스키마"""
    name: str = Field(..., description="역할 이름")
    description: Optional[str] = Field(None, description="역할 설명")


class RoleCreate(RoleBase):
    """역할 생성 스키마"""
    pass


class RoleResponse(InitVarModel):
    """역할 응답 스키마"""
    id: str
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class RoleListResponse(PagedResponse[RoleResponse]):
    """역할 목록 응답 스키마"""
    pass


class UserRoleAssign(BaseModel):
    """사용자에게 역할 할당 스키마"""
    role_name: str = Field(..., description="할당할 역할 이름")


class UserRoleResponse(BaseModel):
    """사용자 역할 응답 스키마"""
    user_id: str
    roles: List[str]