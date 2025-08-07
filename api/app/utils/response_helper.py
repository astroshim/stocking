from fastapi.responses import JSONResponse
from typing import Any, Optional
from http import HTTPStatus

from app.api.schemas.common_response import create_response_model


def create_response(
        data: Any = None,
        status_code: int = HTTPStatus.OK,
        message: Optional[str] = None
) -> JSONResponse:
    """
    표준화된 응답 형식을 생성합니다.

    Args:
        data: 응답 데이터
        status_code: HTTP 상태 코드
        message: 응답 메시지 (없으면 HTTP 상태 메시지 사용)

    Returns:
        표준화된 JSONResponse
    """
    response_data = create_response_model(data, status_code, message)
    return JSONResponse(content=response_data, status_code=status_code, media_type="application/json")
