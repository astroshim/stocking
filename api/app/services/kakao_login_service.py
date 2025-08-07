import logging

import httpx

from app.api.schemas.sns_schema import KakaoTokenResponse, KakaoUserInfo
from app.config import config


class KakaoLoginService:
    def __init__(self):
        self.kakao_auth_url = 'https://kauth.kakao.com/oauth/token'
        self.kakao_user_info_api = "https://kapi.kakao.com/v2/user/me"

    async def get_token(self, code: str) -> KakaoTokenResponse:
        """카카오 인증 코드로 토큰을 요청합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.kakao_auth_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": config.KAKAO_CLIENT_ID,
                    "redirect_uri": config.KAKAO_REDIRECT_URI,
                    "code": code,
                    "client_secret": config.KAKAO_CLIENT_SECRET
                },
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
            )
            response_data = response.json()
            response.raise_for_status()
            logging.debug(f"kakao_token_response: {response_data}")
            return KakaoTokenResponse(**response_data)

    async def get_user_info(self, access_token: str) -> KakaoUserInfo:
        print(f"access_token: {access_token}")

        """카카오 액세스 토큰으로 사용자 정보를 요청합니다."""
        try:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        self.kakao_user_info_api,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-type": "application/x-www-form-urlencoded;charset=utf-8"
                        }
                    )
                    response_data = response.json()
                    logging.debug(f"kakao_user_info_response = {response_data}")

                    response.raise_for_status()
                    return KakaoUserInfo(**response_data)
                except httpx.HTTPStatusError as e:
                    logging.error(f"카카오 로그인 HTTP 상태 코드 오류: {e.response.status_code} - {e.response.text}")
                    # 오류 처리 로직 또는 재시도 로직
                    raise

                except httpx.RequestError as e:
                    logging.error(f"카카오 로그인 요청 오류: {str(e)}")
                    # 네트워크 관련 오류 처리
                    raise

        except httpx.TimeoutException:
            logging.error("카카오 로그인 요청 시간 초과")
            # 타임아웃 처리 로직
            raise

        except Exception as e:
            logging.error(f"카카오 사용자 정보 요청 중 예상치 못한 오류: {str(e)}")
            # 기타 예외 처리
            raise
