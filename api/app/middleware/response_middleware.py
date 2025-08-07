from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import time
from http import HTTPStatus
import json

class StandardResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # 이미 JSONResponse인 경우 내용 추출
        if isinstance(response, JSONResponse):
            # 이미 표준 형식이면 수정하지 않음
            content = json.loads(response.body)
            if "meta" in content and "data" in content:
                return response

            # 표준 형식으로 변환
            standard_content = {
                "meta": {
                    "code": response.status_code,
                    "message": HTTPStatus(response.status_code).phrase,
                    "timestamp": int(time.time())
                },
                "data": content
            }
            return JSONResponse(
                content=standard_content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )

        # 다른 유형의 응답은 그대로 반환
        return response
