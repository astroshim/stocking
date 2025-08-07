from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any


class SocialUserInfo(BaseModel):
    """다양한 소셜 플랫폼의 사용자 정보를 통합하는 모델"""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    profile_image: Optional[str] = None
    social_type: Optional[str] = None
    raw_data: Dict[str, Any]  # 원본 데이터 저장


class KakaoTokenResponse(BaseModel):
    token_type: str
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_token_expires_in: int
    scope: Optional[str] = None


class KakaoUserInfo(BaseModel):
    id: int
    connected_at: str
    properties: Dict[str, Any]
    kakao_account: Dict[str, Any]


class GoogleTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None


class GoogleUserInfo(BaseModel):
    sub: str  # Google의 고유 사용자 ID
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    locale: Optional[str] = None


class AppleTokenResponse(BaseModel):
    """애플 OAuth 토큰 응답 스키마"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    id_token: str


class AppleUserInfo(BaseModel):
    """애플 사용자 정보 스키마"""
    # Apple ID 토큰의 주요 필드
    sub: str  # 사용자 고유 식별자 (Apple의 user ID)
    email: Optional[str] = None  # 사용자 이메일 (최초 로그인시에만 제공될 수 있음)
    email_verified: Optional[bool] = None
    is_private_email: Optional[bool] = None
    name: Optional[Dict[str, str]] = None  # 최초 로그인시에만 제공될 수 있음 (firstName, lastName)
    aud: Optional[str] = None  # audience (client_id)
    iss: Optional[str] = None  # issuer (https://appleid.apple.com)
    exp: Optional[int] = None  # 만료 시간
    iat: Optional[int] = None  # 발급 시간

    # 기타 필요한 필드를 추가할 수 있음
    nonce: Optional[str] = None
    nonce_supported: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        """name 필드 검증 및 기본값 설정"""
        # None이면 빈 딕셔너리로 초기화
        if value is None:
            return {}

        return value
