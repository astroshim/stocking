from fastapi import APIRouter, Depends, status, Request
from fastapi import Query

from app.api.v1.schemas.user_schema import (
    UserCreate, ResponseUser,
    RequestLogin, PushTokenPatch, UserPatch, UserListResponse
)
from app.config.di import get_user_service
from app.config.get_current_user import get_current_user
from app.exceptions.custom_exceptions import APIException
from app.services.user_service import UserService
from app.utils.client_helper import get_client_ip
from app.utils.response_helper import create_response

router = APIRouter()


@router.post("", summary="유저 생성")
def create_user(user_data: UserCreate, user_service: UserService = Depends(get_user_service)):
    """새로운 사용자 생성"""
    # 이미 존재하는 사용자 확인
    existing_user = user_service.get_by_userid(user_data.userid)

    if existing_user:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            message="User ID already exists",
            detail={"userid": user_data.userid}
        )

    existing_email = user_service.get_by_email(user_data.email)
    if existing_email:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            message="Email already exists",
            detail={"email": user_data.email}
        )

    user = user_service.create_user(user_data.dict(exclude_unset=True))

    # 응답 데이터 구성
    user_data = ResponseUser.model_validate(user)

    # 표준화된 응답 생성
    return create_response(
        data=user_data.model_dump(),
        status_code=status.HTTP_201_CREATED,
        message="success"
    )


@router.post("/login", summary="유저 로그인")
def login(login_data: RequestLogin, request: Request, user_service: UserService = Depends(get_user_service)):
    """사용자 로그인"""
    try:
        user = user_service.login(login_data.dict(), client_ip=get_client_ip(request))

        # 응답 데이터 구성
        user_data = ResponseUser.model_validate(user)
        return create_response(
            data=user_data.model_dump(),
            status_code=status.HTTP_201_CREATED,
            message="success"
        )
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed to login user",
            detail={}
        )


@router.post('/push_tokens', summary="푸시 토큰 등록")
def set_push(push_data: PushTokenPatch, user_id: str = Depends(get_current_user), user_service: UserService = Depends(get_user_service)):
    """푸시 토큰 설정"""
    try:
        user = user_service.set_push_token(user_id, push_data.dict())
        return create_response(ResponseUser.model_validate(user).model_dump(), status.HTTP_201_CREATED, "success")

    except Exception as e:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Failed to set push token.",
            detail={}
        )


@router.get('/me', summary="내 정보 조회")
def me(current_user_id: str = Depends(get_current_user), user_service: UserService = Depends(get_user_service)):
    """내 정보 조회"""
    try:
        user = user_service.get_by_id(current_user_id)

        if not user:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found",
                detail={}
            )

        result = ResponseUser.model_validate(user)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve your profile",
            detail={}
        )


@router.get('/{user_id}', summary="사용자 정보 조회")
def show(user_id: str, user_service: UserService = Depends(get_user_service)):
    """사용자 정보 조회"""
    try:
        user = user_service.get_by_id(user_id)

        if not user:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found",
                detail={}
            )

        result = ResponseUser.model_validate(user)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve user",
            detail={}
        )


@router.put('/{user_id}', summary="사용자 정보 수정")
def update(user_id: str, user_data: UserPatch, current_user_id: str = Depends(get_current_user),
           user_service: UserService = Depends(get_user_service)):
    """사용자 정보 수정"""
    try:
        # 권한 확인: 자신의 계정만 수정 가능
        if current_user_id != user_id:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Not authorized",
                detail={}
            )

        # 요청 데이터 검증
        data = user_data.dict(exclude_none=True)

        # 이메일 변경 시 중복 확인
        if 'email' in data:
            existing_email = user_service.get_by_email(data['email'])
            if existing_email and existing_email.id != user_id:
                raise APIException(
                    status_code=status.HTTP_409_CONFLICT,
                    message="Email already exists",
                    detail={"email": data['email']}
                )

        user = user_service.update_user(user_id, data)

        if not user:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found",
                detail={}
            )

        result = ResponseUser.model_validate(user)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update user",
            detail={}
        )


@router.delete('/{user_id}', summary="사용자 삭제")
def delete(user_id: str, current_user_id: str = Depends(get_current_user), user_service: UserService = Depends(get_user_service)):
    """사용자 삭제"""
    try:
        # 권한 확인: 자신의 계정만 삭제 가능 (또는 관리자)
        if current_user_id != user_id:  # 관리자 확인 로직을 추가할 수 있음
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Not authorized",
                detail={}
            )

        success = user_service.delete_user(user_id)

        if not success:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="User not found",
                detail={}
            )

        return create_response({"success": True}, status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete user",
            detail={}
        )


@router.get('', summary="사용자 목록 조회")
def list_users(current_user_id: str = Depends(get_current_user),
               page: int = Query(1, ge=1),
               per_page: int = Query(10, ge=1, le=100),
               user_service: UserService = Depends(get_user_service)):
    """사용자 목록 조회"""
    try:
        paginated = user_service.list_users(page=page, per_page=per_page)
        response = UserListResponse.from_page_result(paginated)
        return create_response(response.model_dump(), status.HTTP_200_OK, "success")
    except Exception as e:
        print(e)
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve users",
            detail={}
        )
