import logging
from fastapi import APIRouter, Depends, status, Query

from app.api.v1.schemas.user_schema import ResponseUser
from app.config.di import get_user_service
from app.exceptions.custom_exceptions import APIException
from app.services.apple_login_service import AppleLoginService
from app.services.user_service import UserService
from app.services.google_login_service import GoogleLoginService
from app.services.kakao_login_service import KakaoLoginService
from app.services.sns_schema_converter import convert_kakao_user_to_social_info, convert_google_user_to_social_info, \
    convert_apple_user_to_social_info
from app.utils.response_helper import create_response

router = APIRouter()


@router.get("/apple/callback", summary="apple redirect url")
async def apple_callback(code: str = Query(...), user_service: UserService = Depends(get_user_service)):
    """애플 콜백 처리 - 인증 코드로 토큰을 요청하고 사용자 정보를 가져옵니다."""
    try:
        # 액세스 토큰 요청
        token_info = await AppleLoginService().get_token(code)
        logging.debug(f"apple token_info: {token_info}")

        # 사용자 정보 요청 (애플은 id_token에서 사용자 정보를 추출)
        user_info = await AppleLoginService().get_user_info(token_info.id_token)
        logging.debug(f"apple user_info: {user_info}")

        # 사용자 정보를 통합 형식으로 변환
        social_user_info = convert_apple_user_to_social_info(user_info.model_dump())
        logging.debug(f"apple social_user_info: {social_user_info}")

        # 사용자 생성 또는 조회
        user = user_service.sns_sign_in(social_user_info)

        # API 응답이 필요한 경우 아래 코드 사용
        user_data = ResponseUser.model_validate(user)
        return create_response(
            data=user_data.model_dump(),
            status_code=status.HTTP_200_OK,
            message="success"
        )
    except Exception as e:
        logging.error(f"애플 로그인 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed to login user",
            detail={}
        )


@router.get("/kakao/callback", summary="kakao redirect url")
async def kaka_callback(code: str = Query(...), user_service: UserService = Depends(get_user_service)):
    """카카오 콜백 처리 - 인증 코드로 토큰을 요청하고 사용자 정보를 가져옵니다."""
    try:
        # 액세스 토큰 요청
        token_info = await KakaoLoginService().get_token(code)

        logging.debug(f"token_info: {token_info}")

        # 사용자 정보 요청
        user_info = await KakaoLoginService().get_user_info(token_info.access_token)

        # 사용자 정보를 통합 형식으로 변환
        social_user_info = convert_kakao_user_to_social_info(user_info)

        logging.debug(f"social_user_info: {social_user_info}")

        # 사용자 생성 또는 조회
        user = user_service.sns_sign_in(social_user_info)

        # API 응답이 필요한 경우 아래 코드 사용
        user_data = ResponseUser.model_validate(user)
        return create_response(
            data=user_data.model_dump(),
            status_code=status.HTTP_200_OK,
            message="success"
        )
    except Exception as e:
        logging.error(f"카카오 로그인 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed to login user",
            detail={}
        )


@router.get("/google/callback", summary="google redirect url")
async def google_callback(code: str = Query(...), user_service: UserService = Depends(get_user_service)):
    try:
        # 액세스 토큰 요청
        token_info = await GoogleLoginService().get_token(code)

        logging.debug(f"token_info: {token_info}")

        # 사용자 정보 요청
        user_info = await GoogleLoginService().get_user_info(token_info.access_token)

        social_user_info = convert_google_user_to_social_info(user_info.model_dump())

        logging.debug(f"social_user_info: {social_user_info}")

        # 사용자 생성 또는 조회
        user = user_service.sns_sign_in(social_user_info)

        # API 응답이 필요한 경우 아래 코드 사용
        user_data = ResponseUser.model_validate(user)
        return create_response(
            data=user_data.model_dump(),
            status_code=status.HTTP_200_OK,
            message="success"
        )
    except Exception as e:
        logging.error(f"구글 로그인 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed to login user",
            detail={str(e) or "Failed to login user" if not str(e) else str(e)}
        )
