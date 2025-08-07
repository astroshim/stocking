import os
from typing import Dict, Any, List
from pydantic import Field
from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """프로덕션 환경 설정"""

    # CORS 설정 (프로덕션 환경 - 보안 강화)
    CORS_ORIGINS: List[str] = [
        "https://stocking-web.vercel.app",  # Vercel 배포 도메인
        "https://stocking.kr",  # 프로덕션 도메인
        "https://www.stocking.kr",
        "https://api.stocking.kr"  # API 도메인 (필요시)
    ]
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = [
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With"
    ]

    # JWT 설정
    JWT_SECRET_KEY: str = '3a9b2c1d7e8f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d'

    # 스토리지 설정
    STORAGE_DOMAIN: str = Field(os.environ.get('STORAGE_DOMAIN') or 'https://stocking.kr')
    STORAGE_BUCKET_NAME: str = Field(os.environ.get('STORAGE_BUCKET_NAME') or 'stocking')

    # # 추가 프로덕션 환경 설정
    # DEBUG: bool = False
    # LOG_LEVEL: str = "INFO"
    # 추가 개발 환경 설정
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"


    AWS_ACCESS_KEY_ID: str = os.environ.get('AWS_ACCESS_KEY_ID', 'AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY: str = os.environ.get('AWS_SECRET_ACCESS_KEY', 'AWS_SECRET_ACCESS_KEY')

    # 프로덕션용 데이터베이스 설정 (필요 시 재정의)
    DATABASE_ENGINE_OPTIONS: Dict[str, Any] = {
        'pool_size': 20,
        'pool_timeout': 60,
        'max_overflow': 256,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 60,
            'read_timeout': 60,
            'write_timeout': 120
        }
    }

    DATABASE_URI: str = 'mysql+pymysql://stocking:aWdj83Kp9dbwlsdktkfkdgodkQkrk6B4N!@dev-mysql-db.ctqke428aiun.ap-northeast-2.rds.amazonaws.com/stocking'

    # 결제 연동 (portone)
    PORTONE_STORE_ID: str = os.environ.get('PORTONE_STORE_ID', 'store-3909c008-6422-4743-a504-dbd27acd8bf6')
    PORTONE_CUSTOMER_CODE: str = os.environ.get('PORTONE_CUSTOMER_CODE', 'imp38612886')
    PORTONE_V1_API_KEY: str = os.environ.get('PORTONE_V1_API_KEY', '8845806176016206')
    PORTONE_V1_API_SECRET: str = os.environ.get('PORTONE_V1_API_SECRET', 'PORTONE_V1_API_SECRET')
    PORTONE_V2_API_SECRET: str = os.environ.get('PORTONE_V2_API_SECRET', 'PORTONE_V2_API_SECRET')
    PORTONE_WEBHOOK_SECRET: str = os.environ.get('PORTONE_WEBHOOK_SECRET', 'PORTONE_WEBHOOK_SECRET')

    # kakao login
    KAKAO_CLIENT_ID: str = os.environ.get('KAKAO_CLIENT_ID', 'KAKAO_CLIENT_ID')
    KAKAO_CLIENT_SECRET: str = os.environ.get('KAKAO_CLIENT_SECRET', 'KAKAO_CLIENT_SECRET')
    KAKAO_REDIRECT_URI: str = os.environ.get('KAKAO_REDIRECT_URI', 'http://localhost:3000/login/kakao')

    # Google login
    GOOGLE_CLIENT_ID: str = os.environ.get('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET: str = os.environ.get('GOOGLE_CLIENT_SECRET', 'GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI: str = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:3000/login/google')

    # Apple login
    APPLE_KEY_ID: str = os.environ.get('APPLE_KEY_ID', 'APPLE_KEY_ID')
    APPLE_TEAM_ID: str = os.environ.get('APPLE_TEAM_ID', 'APPLE_TEAM_ID')
    APPLE_CLIENT_ID: str = os.environ.get('APPLE_CLIENT_ID', 'stocking-web.vercel.app')
    APPLE_REDIRECT_URI: str = os.environ.get('APPLE_REDIRECT_URI', 'https://stocking-web.vercel.app/login/apple')


