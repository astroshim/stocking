import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.api import api_router
from app.utils.error_handlers import register_error_handlers
from app.middleware.response_middleware import StandardResponseMiddleware
from app.api.v1.endpoints import (
    user_controller,
    routine_marketing_controller,
)

def create_app():
    app = FastAPI(
        title="stocking API",
        description="stocking API Documentation",
        version="1.0.0"
    )

    # 미들웨어 등록
    # app.add_middleware(StandardResponseMiddleware)

    # 환경 변수 로깅
    logging.debug(f"Starting application with PYTHON_ENV: {config.PYTHON_ENV}")
    logging.debug(f"DATABASE_URI: {config.DATABASE_URI}")
    logging.debug(f"STORAGE_DOMAIN: {config.STORAGE_DOMAIN}")
    logging.debug(f"CORS_ORIGINS: {config.CORS_ORIGINS}")

    # CORS 설정 (환경별 설정 적용)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],

        # allow_origins=config.CORS_ORIGINS,
        # allow_credentials=config.CORS_ALLOW_CREDENTIALS,
        # allow_methods=config.CORS_ALLOW_METHODS,
        # allow_headers=config.CORS_ALLOW_HEADERS,
        # expose_headers=["Content-Type", "Authorization"],
    )

    # API 라우터 등록
    app.include_router(api_router, prefix="/api")

    # 에러 핸들러 등록
    register_error_handlers(app)

    return app

app = create_app()
