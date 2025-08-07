from datetime import datetime
from fastapi import APIRouter, Depends, Query, status as fastapi_status
from typing import Dict, Any, Optional

from app.api.v1.schemas.report_schema import (
    ReportCreate, ReportStatusUpdate, ReportResponse, ReportListResponse
)
from app.config.get_current_user import get_current_user
from app.config.di import get_report_service, get_role_service
from app.config.role_checker import require_admin, require_moderator
from app.exceptions.custom_exceptions import APIException
from app.services.report_service import ReportService
from app.services.role_service import RoleService
from app.utils.response_helper import create_response

router = APIRouter()


@router.post("",
             summary="신고 생성",
             description="""
    새로운 신고를 생성합니다.

    **reportable_type**:
    
    - verification: 인증에 대한 신고
    - user: 사용자에 대한 신고

    신고 생성 시 자동으로 'pending' 상태로 설정됩니다.
    """
             )
def create(
        report_data: ReportCreate,
        user_id: str = Depends(get_current_user),
        report_service: ReportService = Depends(get_report_service)
):
    """신고 생성 API"""
    try:
        # 현재 로그인한 사용자 ID 설정
        data = report_data.dict(exclude_unset=True)
        data['user_id'] = user_id

        report = report_service.create_report(data)

        result = ReportResponse.model_validate(report)
        return create_response(result.dict(), fastapi_status.HTTP_201_CREATED, "Report created successfully")
    except Exception as e:
        raise APIException(
            status_code=fastapi_status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create report",
            detail={"error": str(e)}
        )


@router.put("/{report_id}/status", summary="신고 상태 업데이트",
            description="""
    신고의 상태를 업데이트합니다. 관리자 또는 중재자 권한이 필요합니다.

    **가능한 상태 값**:
    - pending: 처리 대기
    - in_progress: 처리 중
    - resolved: 해결됨
    - rejected: 거부됨
    """
            )
def update_status(
        report_id: str,
        status_data: ReportStatusUpdate,
        user_id: str = Depends(require_moderator),
        report_service: ReportService = Depends(get_report_service)
):
    """신고 상태 업데이트 API"""
    try:
        # 처리자 정보 기록
        data = status_data.dict(exclude_unset=True)
        data['handled_by'] = user_id
        data['id'] = report_id

        # 신고 처리 수행
        report = report_service.update_status(data)

        if not report:
            return create_response(
                {"error": "Report not found"},
                fastapi_status.HTTP_404_NOT_FOUND,
                "Report not found"
            )

        result = ReportResponse.model_validate(report)
        return create_response(
            result.dict(),
            fastapi_status.HTTP_200_OK,
            "Report status updated successfully"
        )
    except Exception as e:
        raise APIException(
            status_code=fastapi_status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update report status",
            detail={"error": str(e)}
        )


def _build_report_query_params(
        current_user_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        reportable_type: Optional[str] = None,
        reportable_id: Optional[str] = None,
        handled_by: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        per_page: int = 10
) -> Dict[str, Any]:
    """신고 조회를 위한 쿼리 파라미터를 구성하는 헬퍼 함수"""
    arguments = {}

    # 필터 파라미터 추가
    if current_user_id:
        arguments['user_id'] = current_user_id
    if user_id:
        arguments['user_id'] = user_id
    if status:
        arguments['status'] = status
    if reportable_type:
        arguments['reportable_type'] = reportable_type
    if reportable_id:
        arguments['reportable_id'] = reportable_id
    if handled_by:
        arguments['handled_by'] = handled_by
    if start_date:
        arguments['start_date'] = start_date
    if end_date:
        arguments['end_date'] = end_date

    # 정렬 및 페이지네이션 설정
    arguments['sort_by'] = sort_by
    arguments['sort_order'] = sort_order
    arguments['page'] = page
    arguments['per_page'] = per_page

    return arguments


def _get_reports(report_service: ReportService, query_params: Dict[str, Any]):
    """신고 목록을 조회하고 응답을 구성하는 함수"""
    try:
        reports = report_service.list_reports(query_params)
        response = ReportListResponse.from_page_result(reports)
        return create_response(response.model_dump(), fastapi_status.HTTP_200_OK, "success")
    except Exception as e:
        raise APIException(
            status_code=fastapi_status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve reports",
            detail={"error": str(e)}
        )


@router.get("/my", summary="나의 신고 리스트")
def get_my_reports(
        current_user_id: str = Depends(get_current_user),
        user_id: Optional[str] = Query(None, description="신고자 ID로 필터링 (관리자용)"),
        status: Optional[str] = Query(None, description="처리 상태로 필터링(pending, in_progress, resolved, rejected)"),
        reportable_type: Optional[str] = Query(None, description="신고 대상 유형(verification, user)"),
        reportable_id: Optional[str] = Query(None, description="신고 대상 ID"),
        handled_by: Optional[str] = Query(None, description="처리자 ID로 필터링"),
        start_date: Optional[datetime] = Query(None, description="이 날짜 이후 신고만 조회 (created_at 기준)"),
        end_date: Optional[datetime] = Query(None, description="이 날짜 이전 신고만 조회 (created_at 기준)"),
        sort_by: str = Query("created_at", description="정렬 기준 필드"),
        sort_order: str = Query("desc", description="정렬 방향 ('asc' 또는 'desc')"),
        page: int = Query(1, ge=1, description="페이지 번호"),
        per_page: int = Query(10, ge=1, description="페이지당 항목 수"),
        report_service: ReportService = Depends(get_report_service)
):
    """현재 사용자의 신고 목록 조회 API"""
    # 기본적으로 현재 사용자의 신고만 조회
    query_params = _build_report_query_params(
        # user_id가 제공되지 않은 경우 현재 사용자 ID 사용
        current_user_id=None if user_id else current_user_id,
        user_id=user_id,
        status=status,
        reportable_type=reportable_type,
        reportable_id=reportable_id,
        handled_by=handled_by,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    return _get_reports(report_service, query_params)


@router.get("", summary="신고 리스트 조회 (관리자/중재자 전용)",)
def list_reports(
        current_user_id: str = Depends(require_moderator),
        user_id: Optional[str] = Query(None, description="신고자 ID로 필터링"),
        status: Optional[str] = Query(None, description="처리 상태로 필터링(pending, in_progress, resolved, rejected)"),
        reportable_type: Optional[str] = Query(None, description="신고 대상 유형(verification, user)"),
        reportable_id: Optional[str] = Query(None, description="신고 대상 ID"),
        handled_by: Optional[str] = Query(None, description="처리자 ID로 필터링"),
        start_date: Optional[datetime] = Query(None, description="이 날짜 이후 신고만 조회 (created_at 기준)"),
        end_date: Optional[datetime] = Query(None, description="이 날짜 이전 신고만 조회 (created_at 기준)"),
        sort_by: str = Query("created_at", description="정렬 기준 필드"),
        sort_order: str = Query("desc", description="정렬 방향 ('asc' 또는 'desc')"),
        page: int = Query(1, ge=1, description="페이지 번호"),
        per_page: int = Query(10, ge=1, description="페이지당 항목 수"),
        report_service: ReportService = Depends(get_report_service)
):
    """모든 신고 목록 조회 API (관리자용)"""
    # 여기서는 관리자 권한 확인 로직을 추가할 수 있음
    # verify_admin(current_user_id)

    query_params = _build_report_query_params(
        user_id=user_id,
        status=status,
        reportable_type=reportable_type,
        reportable_id=reportable_id,
        handled_by=handled_by,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    return _get_reports(report_service, query_params)


@router.get("/{report_id}", summary="신고 상세 조회")
def show(
        report_id: str,
        user_id: str = Depends(get_current_user),
        report_service: ReportService = Depends(get_report_service),
        role_service: RoleService = Depends(get_role_service)
):
    """특정 신고 조회 API"""
    try:
        report = report_service.get_by_id(report_id)

        if not report:
            return create_response(
                {"error": "Report not found"},
                fastapi_status.HTTP_404_NOT_FOUND,
                "Report not found"
            )

        # 자신의 신고만 볼 수 있게 하거나, 관리자/중재자 권한 확인
        user_roles = role_service.get_user_roles(user_id)

        # 관리자나 중재자가 아니고, 자신의 신고도 아닌 경우 접근 거부
        if report.user_id != user_id and not any(role in ['admin', 'moderator'] for role in user_roles):
            return create_response(
                {"error": "Not authorized"},
                fastapi_status.HTTP_403_FORBIDDEN,
                "Not authorized to view this report"
            )

        result = ReportResponse.model_validate(report)
        return create_response(
            result.dict(),
            fastapi_status.HTTP_200_OK,
            "Report retrieved successfully"
        )
    except Exception as e:
        raise APIException(
            status_code=fastapi_status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve reports",
            detail={"error": str(e)}
        )
