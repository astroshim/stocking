import logging
from fastapi import APIRouter, Depends, Request, Header, status, Query, Path
from typing import Optional

from app.api.v1.schemas.routine_marketing_schema import CreateRoutineMarketing, RoutineMarketingResponse, ClientInfo, RoutineMarketingListResponse
from app.services.routine_marketing_service import RoutineMarketingService
from app.config.di import get_routine_marketing_service
from app.utils.response_helper import create_response
from app.exceptions.custom_exceptions import APIException

router = APIRouter()

@router.post("", summary="루틴 마케팅 정보 생성")
def create_routine_marketing(
    routine_marketing_data: CreateRoutineMarketing,
    request: Request,
    service: RoutineMarketingService = Depends(get_routine_marketing_service)
):
    try:
        """
        루틴 마케팅 정보를 생성합니다.
        """
        # 쿠키를 제외한 헤더 정보만 수집
        filtered_headers = {key: value for key, value in request.headers.items() if key.lower() != 'cookie'}
        
        client_info = ClientInfo(
            ip=request.client.host,
            user_client_info=str(filtered_headers)  # 쿠키를 제외한 헤더를 문자열로 저장
        )
        
        created_obj = service.create_routine_marketing(routine_marketing_data, client_info)
        
        return create_response(
            RoutineMarketingResponse.model_validate(created_obj).model_dump(),
            status.HTTP_200_OK,
            "success"
        )
        
    except Exception as e:
        logging.error(f"루틴 마케팅 정보 저장 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create routine marketing data",
            detail={"error": str(e)}
        )

@router.get("", summary="루틴 마케팅 정보 리스트 조회")
def list_routine_marketing(
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(10, ge=1, le=100, description="페이지당 아이템 수"),
    service: RoutineMarketingService = Depends(get_routine_marketing_service)
):
    try:
        """
        루틴 마케팅 정보 리스트를 페이징 처리하여 조회합니다.
        """
        result = service.list_routine_marketing(page, per_page)
        response = RoutineMarketingListResponse.from_page_result(result)
        
        return create_response(
            response.model_dump(),
            status.HTTP_200_OK,
            "success"
        )
        
    except Exception as e:
        logging.error(f"루틴 마케팅 정보 리스트 조회 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve routine marketing list",
            detail={"error": str(e)}
        )

@router.get("/{routine_marketing_id}", summary="루틴 마케팅 정보 단일 조회")
def get_routine_marketing(
    routine_marketing_id: str = Path(..., description="루틴 마케팅 ID"),
    service: RoutineMarketingService = Depends(get_routine_marketing_service)
):
    try:
        """
        ID로 루틴 마케팅 정보를 조회합니다.
        """
        routine_marketing = service.get_routine_marketing_by_id(routine_marketing_id)
        
        if not routine_marketing:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Routine marketing data not found",
                detail={"id": routine_marketing_id}
            )
        
        return create_response(
            RoutineMarketingResponse.model_validate(routine_marketing).model_dump(),
            status.HTTP_200_OK,
            "success"
        )
        
    except APIException:
        raise
    except Exception as e:
        logging.error(f"루틴 마케팅 정보 조회 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve routine marketing data",
            detail={"error": str(e)}
        )

@router.delete("/{routine_marketing_id}", summary="루틴 마케팅 정보 삭제")
def delete_routine_marketing(
    routine_marketing_id: str = Path(..., description="루틴 마케팅 ID"),
    service: RoutineMarketingService = Depends(get_routine_marketing_service)
):
    try:
        """
        ID로 루틴 마케팅 정보를 삭제합니다.
        """
        success = service.delete_routine_marketing(routine_marketing_id)
        
        if not success:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Routine marketing data not found",
                detail={"id": routine_marketing_id}
            )
        
        return create_response(
            {"id": routine_marketing_id, "deleted": True},
            status.HTTP_200_OK,
            "success"
        )
        
    except APIException:
        raise
    except Exception as e:
        logging.error(f"루틴 마케팅 정보 삭제 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete routine marketing data",
            detail={"error": str(e)}
        )