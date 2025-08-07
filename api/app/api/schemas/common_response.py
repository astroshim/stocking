from typing import Any, Dict
import time
import json
from http import HTTPStatus
from typing import TypeVar, Generic, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')


class ResponseMeta(BaseModel):
    code: int = Field(..., description="HTTP 상태 코드")
    message: str = Field(..., description="응답 메시지")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="응답 타임스탬프")


class StandardResponse(BaseModel, Generic[T]):
    meta: ResponseMeta
    data: T


def serialize_safe(obj: Any) -> Any:
    """모든 객체를 JSON 직렬화 가능한 형태로 변환"""
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, dict):
            return {k: serialize_safe(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [serialize_safe(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(serialize_safe(v) for v in obj)
        elif isinstance(obj, BaseException):
            return str(obj)
        else:
            return str(obj)


def create_response_model(
        data: Any = None,
        status_code: int = HTTPStatus.OK,
        message: Optional[str] = None
) -> Dict:
    """
    표준화된 응답 모델 데이터를 생성합니다.
    """
    return {
        "meta": {
            "code": status_code,
            "message": message or HTTPStatus(status_code).phrase,
            "timestamp": int(time.time())
        },
        "data": serialize_safe(data)
    }

