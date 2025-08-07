from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


# 열거형 정의 (필드 유효성 검사에 사용)
class ReportableType(str, Enum):
    VERIFICATION = "verification"
    USER = "user"


class ReportStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReportCreate(BaseModel):
    """신고 생성 모델"""
    reportable_type: ReportableType = Field(..., description="신고 대상 유형 (verification, user)")
    reportable_id: str = Field(..., description="신고 대상의 ID")

    reason: str = Field(
        ...,
        description="신고 사유",
        examples=["불적절한 내용", "스팸", "사기 행위"]
    )
    description: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reportable_type": "verification",
                    "reportable_id": "1234-5678-90ab-cdef",
                    "reason": "불적절한 내용",
                    "description": "이 챌린지는 위험한 행동을 조장합니다."
                }
            ]
        },
        "from_attributes": True
    }


class ReportStatusUpdate(BaseModel):
    """신고 상태 업데이트 모델"""
    status: ReportStatus = Field(..., description="신고 상태 (pending, in_progress, resolved, rejected)",
                                 examples=["pending", "in_progress", "resolved", "rejected"])
    handler_comment: str = Field(
        ...,
        description="처리자 코멘트",
        examples=["신고가 접수 되었습니다.", "신고된 내용에 문제가 없습니다."]
    )

    model_config = {
        "from_attributes": True
    }


class ReportStatusHistory(InitVarModel):
    """신고 상태 이력 모델"""
    status: str
    handler_comment: str = ""
    handled_by: str = ""
    handled_at: int

    model_config = {
        "from_attributes": True
    }

    _timestamp_fields = {'handled_at'}


class ReportResponse(InitVarModel):
    """신고 응답 모델"""
    id: str
    user_id: str
    reportable_type: str
    reportable_id: str
    reason: str = ""
    description: str = ""
    status: str = ""
    handler_comment: str = ""
    handled_by: str = ""
    handled_at: Optional[datetime] = None
    created_at: int
    updated_at: int
    status_histories: List[ReportStatusHistory] = [] # 신고 이력
    # last_status_history: Optional[ReportStatusHistory] = {} # 신고의 마지막 상태 이력

    model_config = {
        "from_attributes": True
    }

    _timestamp_fields = {'created_at', 'updated_at', 'handled_at'}
    _default_values = {
        'handler_comment': '', 'handled_by': ''
    }

    # # 필요한 경우 모델의 필드와 ORM 객체의 속성 간 매핑을 제공
    # # 예: ORM 객체의 'last_status_history' 속성을 'last_status' 필드로 매핑
    # @classmethod
    # def from_orm(cls, obj):
    #     if hasattr(obj, 'last_status_history'):
    #         obj.last_status = obj.last_status_history
    #     return super().from_orm(obj)


class ReportListItem(InitVarModel):
    """신고 목록 항목 모델"""
    id: str
    user_id: str
    reportable_type: str = ""
    reportable_id: str = ""
    reason: str
    status: str
    created_at: int
    updated_at: int

    model_config = {
        "from_attributes": True
    }

    _timestamp_fields = {'created_at', 'updated_at'}
    # 다른 필드의 기본값
    _default_values = {
        'reportable_type': "",
    }


# class ReportListResponse(BaseModel):
#     """신고 목록 응답 모델"""
#     items: List[ReportResponse]
#
#     model_config = {
#         "from_attributes": True
#     }
class ReportListResponse(PagedResponse[ReportResponse]):
    """페이징된 목록 응답"""
    pass
