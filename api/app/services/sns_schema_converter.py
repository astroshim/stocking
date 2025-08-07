from app.api.schemas.sns_schema import SocialUserInfo


def convert_kakao_user_to_social_info(kakao_user_info) -> SocialUserInfo:
    """카카오 사용자 정보를 통합 모델로 변환"""
    return SocialUserInfo(
        id=str(kakao_user_info.id),
        email=kakao_user_info.kakao_account.get("email"),
        name=kakao_user_info.properties.get("nickname"),
        profile_image=kakao_user_info.properties.get("profile_image"),
        social_type="KAKAO",
        raw_data=kakao_user_info.dict()
    )


def convert_naver_user_to_social_info(naver_user_info) -> SocialUserInfo:
    """네이버 사용자 정보를 통합 모델로 변환"""
    response = naver_user_info.get("response", {})
    return SocialUserInfo(
        id=response.get("id"),
        email=response.get("email"),
        name=response.get("name"),
        profile_image=response.get("profile_image"),
        social_type="NAVER",
        raw_data=naver_user_info
    )


def convert_google_user_to_social_info(google_user_info) -> SocialUserInfo:
    """구글 사용자 정보를 통합 모델로 변환"""
    return SocialUserInfo(
        id=google_user_info.get("sub"),
        email=google_user_info.get("email"),
        name=google_user_info.get("name"),
        profile_image=google_user_info.get("picture"),
        social_type="GOOGLE",
        raw_data=google_user_info
    )


def convert_apple_user_to_social_info(apple_user_info) -> SocialUserInfo:
    """애플 사용자 정보를 통합 모델로 변환"""

    # name 필드 안전하게 처리
    name_dict = apple_user_info.get("name") or {}
    first_name = name_dict.get("firstName", "")
    last_name = name_dict.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or None

    # 애플은 최초 로그인시에만 이름과 이메일을 제공하는 특이사항 있음
    return SocialUserInfo(
        id=apple_user_info.get("sub"),
        email=apple_user_info.get("email"),
        name=full_name,
        profile_image=None,  # 애플은 프로필 이미지 제공 안함
        social_type="APPLE",
        raw_data=apple_user_info
    )
