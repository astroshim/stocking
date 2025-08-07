from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.v1.schemas.comment_schema import (
    CommentCreate, CommentUpdate, CommentResponse, CommentListResponse, CommentWithChildren
)
from app.config.get_current_user import get_current_user
from app.config.di import get_comment_service
from app.exceptions.custom_exceptions import APIException
from app.services.comment_service import CommentService
from app.utils.response_helper import create_response

router = APIRouter()


@router.post("",
             summary="코멘트 생성",
             description="""
    새로운 코멘트를 생성합니다.

    **commentable_type**:
    
    - verification: 인증에 대한 코멘트

    **parent_id**가 제공되면 해당 코멘트의 답글로 생성됩니다.
    """
             )
def create(
        comment_data: CommentCreate,
        user_id: str = Depends(get_current_user),
        comment_service: CommentService = Depends(get_comment_service)
):
    """코멘트 생성 API"""
    try:
        # 현재 로그인한 사용자 ID 설정
        data = comment_data.model_dump(exclude_unset=True)
        data['user_id'] = user_id

        comment = comment_service.create_comment(**data)

        result = CommentResponse.model_validate(comment)
        return create_response(result.model_dump(), status.HTTP_201_CREATED, "success")
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create comment",
            detail={str(e)}
        )


@router.put("/{comment_id}",
            summary="코멘트 수정",
            description="자신의 코멘트만 수정할 수 있습니다.")
def update(
        comment_id: str,
        comment_data: CommentUpdate,
        user_id: str = Depends(get_current_user),
        comment_service: CommentService = Depends(get_comment_service)
):
    """코멘트 수정 API"""
    try:
        data = comment_data.model_dump(exclude_unset=True)
        data['id'] = comment_id
        data['user_id'] = user_id

        comment = comment_service.update_comment(**data)

        if not comment:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Comment not found or you are not authorized to edit this comment",
                detail={}
            )

        result = CommentResponse.model_validate(comment)
        return create_response(
            result.model_dump(),
            status.HTTP_200_OK,
            "success"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update comment",
            detail={str(e)}
        )


@router.delete("/{comment_id}",
               summary="코멘트 삭제",
               description="자신의 코멘트만 삭제할 수 있습니다.")
def destroy(
        comment_id: str,
        user_id: str = Depends(get_current_user),
        comment_service: CommentService = Depends(get_comment_service)
):
    """코멘트 삭제 API"""
    try:
        success = comment_service.delete_comment(user_id, comment_id)
        if not success:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Comment not found or you are not authorized to delete this comment",
                detail={}
            )
        return create_response({}, status.HTTP_200_OK, "success")
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete comment",
            detail={str(e)}
        )


@router.get("",
            summary="코멘트 목록 조회",
            description="""
코멘트 목록을 조회합니다.

**commentable_type**과 **commentable_id**로 특정 대상의 코멘트를 조회할 수 있습니다.
**include_replies**가 True이면 대댓글도 함께 조회합니다.
"""
            )
def index(
        user_id: str = Depends(get_current_user),
        commentable_type: Optional[str] = Query(None, description="코멘트 대상 타입 (verification)"),
        commentable_id: Optional[str] = Query(None, description="코멘트 대상 ID"),
        parent_id: Optional[str] = Query(None, description="부모 코멘트 ID (대댓글 필터링)"),
        include_replies: bool = Query(False, description="대댓글 포함 여부"),
        page: int = Query(1, ge=1, description="페이지 번호"),
        per_page: int = Query(10, ge=1, le=100, description="페이지당 항목 수"),
        # sort_by: str = Query("created_at", description="정렬 기준 필드"),
        # sort_order: str = Query("desc", description="정렬 방향 (asc, desc)"),
        comment_service: CommentService = Depends(get_comment_service)
):
    """코멘트 목록 조회 API"""
    try:
        filters = {
            "commentable_type": commentable_type,
            "commentable_id": commentable_id,
            "parent_id": parent_id,
            "include_replies": include_replies,
            "page": page,
            "per_page": per_page,
            # "sort_by": sort_by,
            # "sort_order": sort_order
        }

        comments_page = comment_service.list_comments(filters)
        result = CommentListResponse.from_page_result(comments_page)

        return create_response(
            result.model_dump(),
            status.HTTP_200_OK,
            "success"
        )
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve comments",
            detail={str(e)}
        )


@router.get("/{comment_id}",
            summary="코멘트 상세 조회",
            description="특정 코멘트의 상세 정보를 조회합니다.")
def show(
        comment_id: str,
        include_replies: bool = Query(False, description="대댓글 포함 여부"),
        comment_service: CommentService = Depends(get_comment_service)
):
    """코멘트 상세 조회 API"""
    try:
        comment = comment_service.get_comment_with_replies(comment_id, include_replies)

        if not comment:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Comment not found",
                detail={}
            )

        return create_response(
            comment,
            status.HTTP_200_OK,
            "success"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve comment",
            detail={str(e)}
        )
