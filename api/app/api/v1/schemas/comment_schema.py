from typing import Optional, List, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class CommentableType(str, Enum):
    VERIFICATION = "verification"


class CommentCreate(BaseModel):
    """코멘트 생성 모델"""
    commentable_type: CommentableType = Field(..., description="코멘트 대상 유형 (verification)")
    commentable_id: str = Field(..., description="코멘트 대상의 ID")
    content: str = Field(..., description="코멘트 내용")
    parent_id: Optional[str] = Field(None, description="부모 코멘트 ID (답글인 경우)")
    is_question: bool = Field(True, description="질문이면 True, 답변이면 False")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "commentable_type": "verification",
                    "commentable_id": "1234-5678-90ab-cdef",
                    "content": "이 챌린지는 어떤 목표를 가지고 있나요?",
                    "parent_id": None,
                    "is_question": True
                }
            ]
        },
        "from_attributes": True
    }


class CommentUpdate(BaseModel):
    """코멘트 수정 모델"""
    content: str = Field(..., description="코멘트 내용")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "수정된 코멘트 내용입니다."
                }
            ]
        },
        "from_attributes": True
    }


class CommentResponse(InitVarModel):
    """코멘트 응답 모델"""
    id: str
    user_id: Optional[str] = None
    commentable_type: str
    commentable_id: str
    content: str
    ancestry: Optional[str] = None
    ancestry_depth: int = 0
    children_count: int = 0
    is_question: bool = True
    answer_name: str = ""
    created_at: int
    updated_at: int

    model_config = {
        "from_attributes": True
    }

    _timestamp_fields = {'created_at', 'updated_at'}
    _default_values = {
        'ancestry': None,
        'answer_name': ''
    }


class CommentWithChildren(CommentResponse):
    """자식 코멘트를 포함한 코멘트 응답 모델"""
    children: List[CommentResponse] = []

    model_config = {
        "from_attributes": True
    }


class CommentListResponse(PagedResponse[CommentResponse]):
    """페이징된 코멘트 목록 응답"""
    pass
