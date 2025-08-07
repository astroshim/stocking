from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from pydantic import ValidationError

from app.api.schemas.common_response import create_response_model
from app.exceptions.custom_exceptions import APIException

def register_error_handlers(app: FastAPI) -> None:
    """
    FastAPI 애플리케이션에 전역 예외 핸들러를 등록합니다.
    모든 예외를 표준 응답 형식으로 변환합니다.
    """

    @app.exception_handler(APIException)
    async def custom_api_exception_handler(request: Request, exc: APIException):
        """커스텀 API 예외 처리"""
        response_data = create_response_model(
            data={"detail": exc.detail},
            status_code=exc.status_code,
            message=exc.message
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTP 예외 처리"""
        response_data = create_response_model(
            data={"detail": exc.detail},
            status_code=exc.status_code
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """요청 유효성 검증 예외 처리"""
        response_data = create_response_model(
            data={"detail": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation Error"
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_data
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Pydantic 유효성 검증 예외 처리"""
        response_data = create_response_model(
            data={"detail": exc.errors()},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation Error"
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_data
        )

    @app.exception_handler(NoResultFound)
    async def not_found_exception_handler(request: Request, exc: NoResultFound):
        """데이터가 없는 경우 처리"""
        response_data = create_response_model(
            data={"detail": "The requested resource was not found"},
            status_code=status.HTTP_404_NOT_FOUND,
            message="Resource Not Found"
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=response_data
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """데이터베이스 예외 처리"""
        response_data = create_response_model(
            data={"detail": str(exc)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Database Error"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """모든 처리되지 않은 예외 처리"""
        response_data = create_response_model(
            data={"detail": str(exc)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal Server Error"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data
        )
