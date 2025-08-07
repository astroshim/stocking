from fastapi import APIRouter, Depends, Query, status

from app.api.v1.schemas.notice_schema import NoticeCreate, NoticeUpdate, \
    NoticeListResponse, notice_to_response
from app.config.get_current_user import get_current_user
from app.config.di import get_notice_service
from app.exceptions.custom_exceptions import APIException
from app.services.notice_service import NoticeService
from app.utils.response_helper import create_response

router = APIRouter()


@router.post("", summary="공지사항 생성", description="""
    새로운 공지사항을 생성합니다.

    ***컬럼 설명***
    - title: "공지사항 제목"
    - content: "공지사항 내용"
    - is_active: "활성화 여부", example=True
""")
def create(
        notice_data: NoticeCreate,
        user_id: str = Depends(get_current_user),
        notice_service: NoticeService = Depends(get_notice_service)
):
    try:
        notice = notice_service.create_notice(user_id, notice_data.model_dump(exclude_unset=True))
        result = notice_to_response(notice)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create notice",
            detail={str(e)}
        )


@router.put("/{notice_id}", summary="공지사항 수정")
def update(
        notice_id: str,
        notice_data: NoticeUpdate,
        current_user_id: str = Depends(get_current_user),
        notice_service: NoticeService = Depends(get_notice_service)
):
    try:
        notice = notice_service.update_notice(notice_id,
                                              notice_data.model_dump(exclude_unset=True))
        if not notice:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notice not found",
                detail={}
            )
        result = notice_to_response(notice)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update notice",
            detail={str(e)}
        )


@router.get("/{notice_id}", summary="공지사항 상세 조회")
def show(
        notice_id: str,
        current_user_id: str = Depends(get_current_user),
        notice_service: NoticeService = Depends(get_notice_service)
):
    try:
        notice = notice_service.get_notice_by_id(notice_id)
        if not notice:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notice not found",
                detail={}
            )

        result = notice_to_response(notice)
        return create_response(result.model_dump(), status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get notice",
            detail={str(e)}
        )


@router.delete("/{notice_id}", summary="공지사항 삭제")
def destroy(
        notice_id: str,
        user_id: str = Depends(get_current_user),
        notice_service: NoticeService = Depends(get_notice_service)
):
    try:
        success = notice_service.delete_notice(user_id, notice_id)
        if not success:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Notice not found",
                detail={}
            )
        return create_response({}, status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete notice",
            detail={str(e)}
        )


@router.get("", summary="공지사항 목록 조회")
def list_notices(
        state: str = Query("all"),
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        notice_service: NoticeService = Depends(get_notice_service)
):
    try:
        paginated = notice_service.list_notices(state, page, per_page)
        response = NoticeListResponse.from_page_result(paginated)
        return create_response(response.model_dump(), status.HTTP_200_OK, "success")
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list notices",
            detail={str(e)}
        )