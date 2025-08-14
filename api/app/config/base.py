import os
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Any, List

class BaseConfig(BaseSettings):
    """기본 설정 클래스"""

    # 환경 설정
    PYTHON_ENV: str = Field(os.environ.get('PYTHON_ENV', 'development'), env="PYTHON_ENV")

    # CORS 설정
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # JWT 설정
    JWT_ALGORITHM: str = 'HS256'
    JWT_SECRET_KEY: str = ""

    # 데이터베이스 설정
    DATABASE_URI: str = ""

    # 데이터베이스 연결 옵션
    DATABASE_ENGINE_OPTIONS: Dict[str, Any] = {
        'pool_size': 10,
        'pool_timeout': 60,
        'max_overflow': 128,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 60,
            'read_timeout': 60,
            'write_timeout': 120
        }
    }

    # 스토리지 설정
    STORAGE_DOMAIN: str = ""
    STORAGE_BUCKET_NAME: str = ""

    # KIS Open Trading API (환경별 설정으로 이동)
    KIS_APP_KEY: str = ""
    KIS_APP_SECRET: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
