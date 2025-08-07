import logging
import jwt
import time
import uuid
import httpx

from app.api.schemas.sns_schema import AppleTokenResponse, AppleUserInfo
from app.config import config


class AppleLoginService:
    def __init__(self):
        self.apple_auth_url = 'https://appleid.apple.com/auth/token'
        self.apple_keys_url = 'https://appleid.apple.com/auth/keys'

    async def get_token(self, code: str) -> AppleTokenResponse:
        """애플 인증 코드로 토큰을 요청합니다."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.apple_auth_url,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": config.APPLE_CLIENT_ID,
                        "client_secret": await self._create_client_secret(),
                        "redirect_uri": config.APPLE_REDIRECT_URI,
                        "code": code
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()

                response_data = response.json()
                logging.debug(f"apple_token_response: {response_data}")
                return AppleTokenResponse(**response_data)

            except httpx.HTTPStatusError as e:
                logging.error(f"애플 토큰 요청 HTTP 상태 코드 오류: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logging.error(f"애플 토큰 요청 중 예상치 못한 오류: {str(e)}")
                raise

    async def get_user_info(self, id_token: str) -> AppleUserInfo:
        """애플 ID 토큰을 검증하고 사용자 정보를 추출합니다."""
        try:
            # ID 토큰 디코딩 (검증은 생략, 필요시 구현)
            # 실제로는 Apple의 public key로 검증해야 함
            payload = jwt.decode(id_token, options={"verify_signature": False})
            logging.debug(f"애플 사용자 정보 페이로드: {payload}")

            # 애플은 최초 로그인시에만 email, name을 제공
            return AppleUserInfo(**payload)

        except jwt.PyJWTError as e:
            logging.error(f"애플 ID 토큰 디코딩 오류: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"애플 사용자 정보 처리 중 예상치 못한 오류: {str(e)}")
            raise

    async def _create_client_secret(self) -> str:
        """애플 로그인용 client_secret JWT 생성"""
        now = int(time.time())

        # JWT 페이로드 생성
        payload = {
            'iss': config.APPLE_TEAM_ID,
            'iat': now,
            'exp': now + 3600,  # 1시간 유효
            'aud': 'https://appleid.apple.com',
            'sub': config.APPLE_CLIENT_ID,
            'jti': str(uuid.uuid4())
        }

        # 개인키는 별도로 관리되어야 함 (예: 환경변수 또는 안전한 저장소에서 로드)
        # 현재 예시에서는 구현되어 있지 않음
        private_key = self._get_private_key()

        # JWT 토큰 생성
        client_secret = jwt.encode(
            payload,
            private_key,
            algorithm='ES256',
            headers={
                'kid': config.APPLE_KEY_ID
            }
        )

        return client_secret

    def _get_private_key(self) -> str:
        """애플 개인 키를 읽어옵니다."""
        # 실제 구현에서는 안전한 위치에서 키 로드
        # 예: 환경 변수, AWS Secrets Manager, 파일 시스템 등

        private_key_path = f"/app/devops/AuthKey_{config.APPLE_KEY_ID}.p8"
        try:
            with open(private_key_path, "r") as key_file:
                return key_file.read()
        except FileNotFoundError:
            logging.error(f"애플 개인 키 파일을 찾을 수 없습니다: {private_key_path}")
            raise