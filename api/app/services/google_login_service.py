import logging

import httpx

from app.api.schemas.sns_schema import GoogleTokenResponse, GoogleUserInfo
from app.config import config


class GoogleLoginService:
    def __init__(self):
        self.google_auth_url = 'https://oauth2.googleapis.com/token'
        self.google_user_info_api = 'https://www.googleapis.com/oauth2/v3/userinfo'

    async def get_token(self, code: str) -> GoogleTokenResponse:
        """구글 인증 코드로 토큰을 요청합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.google_auth_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": config.GOOGLE_REDIRECT_URI,
                    "code": code
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()

            response_data = response.json()
            logging.debug(f"google_token_response: {response_data}")
            return GoogleTokenResponse(**response_data)

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """구글 액세스 토큰으로 사용자 정보를 요청합니다."""
        try:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        self.google_user_info_api,
                        headers={
                            "Authorization": f"Bearer {access_token}"
                        }
                    )
                    response_data = response.json()
                    logging.debug(f"구글 사용자 정보 응답 상태 코드: {response.status_code}")
                    logging.debug(f"구글 사용자 정보 응답: {response_data}")

                    response.raise_for_status()
                    return GoogleUserInfo(**response_data)
                except httpx.HTTPStatusError as e:
                    logging.error(f"구글 로그인 HTTP 상태 코드 오류: {e.response.status_code} - {e.response.text}")
                    raise

                except httpx.RequestError as e:
                    logging.error(f"구글 로그인 요청 오류: {str(e)}")
                    raise

        except httpx.TimeoutException:
            logging.error("구글 로그인 요청 시간 초과")
            raise

        except Exception as e:
            logging.error(f"구글 사용자 정보 요청 중 예상치 못한 오류: {str(e)}")
            raise
