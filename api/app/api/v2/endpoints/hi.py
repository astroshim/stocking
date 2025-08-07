from fastapi import APIRouter, status
from typing import Dict

from starlette.responses import JSONResponse

from app.exceptions.custom_exceptions import APIException
from app.utils.response_helper import create_response

router = APIRouter()

@router.get("")
async def hello() -> JSONResponse:
    """
    간단한 인사 엔드포인트

    Returns:
        Dict[str, Any]: 버전 정보가 포함된 응답
    """
    try:
        return create_response({"version": "hi v2"}, status.HTTP_200_OK, "success")
    except Exception as err:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed",
            detail={}
        )


