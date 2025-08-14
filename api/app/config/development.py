import os
from pydantic import Field
from typing import List
from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    def __init__(self):
        super().__init__()

    """개발 환경 설정"""

    # CORS 설정 (개발 환경)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js 개발 서버
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://stocking-web.vercel.app",  # Vercel 배포 도메인
        "https://stocking.kr",  # 프로덕션 도메인
        "https://www.stocking.kr"
    ]

    # JWT 설정
    JWT_SECRET_KEY: str = '8f4e91c6b0a52d7e5df3c8e7a9f6b02c1d380f5c2a63e94d70b8c7e9f5a2d1e0c3b6a9d2e5f8c1b4a7d0e3f6c9b2a5d8e1f4c7b0a3d6e9f2c5b8a1d4e7f0c3b6'

    # 스토리지 설정
    STORAGE_DOMAIN: str = Field(os.environ.get('STORAGE_DOMAIN') or 'https://stocking.kr')
    STORAGE_BUCKET_NAME: str = Field(os.environ.get('STORAGE_BUCKET_NAME') or 'stocking')

    AWS_ACCESS_KEY_ID: str = os.environ.get('AWS_ACCESS_KEY_ID', 'AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY: str = os.environ.get('AWS_SECRET_ACCESS_KEY', 'AWS_SECRET_ACCESS_KEY')

    # 추가 개발 환경 설정
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    DATABASE_URI: str = 'mysql+pymysql://stocking:LV9Q40QJEnE82LCNGTSL6OK4zgAgduga!@127.0.0.1/stocking'

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
    KAKAO_REDIRECT_URI: str = os.environ.get('KAKAO_REDIRECT_URI', 'http://localhost:5100/api/v1/auth/kakao/callback')

    # Google login
    GOOGLE_CLIENT_ID: str = os.environ.get('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET: str = os.environ.get('GOOGLE_CLIENT_SECRET', 'GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI: str = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5100/api/v1/auth/google/callback')

    # Apple login
    APPLE_KEY_ID: str = os.environ.get('APPLE_KEY_ID', 'APPLE_KEY_ID')
    APPLE_TEAM_ID: str = os.environ.get('APPLE_TEAM_ID', 'APPLE_TEAM_ID')
    APPLE_CLIENT_ID: str = os.environ.get('APPLE_CLIENT_ID', 'stocking-web.vercel.app')
    APPLE_REDIRECT_URI: str = os.environ.get('APPLE_REDIRECT_URI', 'https://stocking-web.vercel.app/login/apple')

    # KIS Open Trading API
    KIS_APP_KEY: str = 'PSn8Hv1BqnAoXrGSItikPYOzPrp1nypiznY1'
    KIS_APP_SECRET: str = 'iR4J7O7yHS+RsVdGOLAutQyDIMWWYTG6o2DQSD2bFFpWcgCQdhbKYCYd5UfBr6UEzODcyXgUwKWwuvX+JPUsysNHjHzcHix+KlJD/FIVSWwbGvV6gdlrr0gTvXDvpdgSV0XNBStcRNCckKr2w5zMhsODIr8YuOixqBQKSRji0ihfXihn2p4='
