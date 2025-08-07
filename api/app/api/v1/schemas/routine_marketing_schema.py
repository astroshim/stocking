from pydantic import BaseModel, EmailStr, HttpUrl, model_validator, field_validator
from typing import Optional
from datetime import datetime
from app.api.schemas.common_pagenation import PagedResponse

class RoutineMarketingBase(BaseModel):
    email: EmailStr
    country: str
    skin_type: str
    product_name: Optional[str] = None
    product_image_url: Optional[HttpUrl] = None

    @field_validator('product_name', mode='before')
    @classmethod
    def validate_product_name(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == "":
            return None
        return v

    @field_validator('product_image_url', mode='before')
    @classmethod
    def validate_product_image_url(cls, v):
        """빈 문자열을 None으로 변환"""
        if v == "":
            return None
        return v

class ClientInfo(BaseModel):
    ip: Optional[str] = None
    user_client_info: Optional[str] = None

class CreateRoutineMarketing(RoutineMarketingBase):
    @model_validator(mode='after')
    def validate_product_info(self):
        """product_name 또는 product_image_url 중 적어도 하나는 입력되어야 합니다."""
        if not self.product_name and not self.product_image_url:
            raise ValueError("product_name 또는 product_image_url 중 적어도 하나는 입력되어야 합니다.")
        return self

class RoutineMarketingResponse(RoutineMarketingBase):
    id: str
    ip: str
    user_client_info: str
    created_at: datetime
    updated_at: datetime
    model_config = {'from_attributes': True}

class RoutineMarketingListResponse(PagedResponse[RoutineMarketingResponse]):
    pass 