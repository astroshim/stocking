import logging
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.v1.schemas.role_schema import RoleCreate, RoleResponse, UserRoleAssign, UserRoleResponse
from app.config.di import get_role_service
from app.config.role_checker import require_admin, get_user_roles
from app.db.models.role import RoleEnum
from app.exceptions.custom_exceptions import APIException
from app.services.role_service import RoleService
from app.utils.response_helper import create_response

router = APIRouter()


@router.get("/available", summary="사용 가능한 역할 목록 조회")
async def list_available_roles():
    """시스템에서 사용 가능한 모든 역할 목록을 반환합니다."""
    roles = [role.value for role in RoleEnum]
    return create_response(
        data=roles,
        status_code=status.HTTP_200_OK,
        message="Available roles retrieved successfully"
    )


@router.get("", summary="역할 목록 조회", dependencies=[Depends(require_admin)])
async def list_roles(role_service: RoleService = Depends(get_role_service)):
    """시스템에 등록된 모든 역할 목록을 반환합니다. (관리자 전용)"""
    try:
        roles = role_service.list_roles()
        
        role_responses = [RoleResponse.model_validate(role) for role in roles]
        return create_response(
            data=[r.model_dump() for r in role_responses],
            status_code=status.HTTP_200_OK,
            message="Roles retrieved successfully"
        )
    except Exception as e:
        logging.error(f"역할 목록 조회 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve roles",
            detail={"error": str(e)}
        )


@router.post("", summary="새 역할 생성", dependencies=[Depends(require_admin)])
async def create_role(role_data: RoleCreate, role_service: RoleService = Depends(get_role_service)):
    """새로운 역할을 생성합니다. (관리자 전용)"""
    try:
        role = role_service.create_role(role_data.model_dump())
        
        role_response = RoleResponse.model_validate(role)
        return create_response(
            data=role_response.model_dump(),
            status_code=status.HTTP_201_CREATED,
            message="Role created successfully"
        )
    except Exception as e:
        logging.error(f"역할 생성 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create role",
            detail={"error": str(e)}
        )


@router.get("/users/{user_id}", summary="사용자 역할 조회", dependencies=[Depends(require_admin)])
async def get_user_roles_endpoint(user_id: str, role_service: RoleService = Depends(get_role_service)):
    """특정 사용자의 역할 목록을 조회합니다. (관리자 전용)"""
    try:
        roles = role_service.get_user_roles(user_id)
        
        return create_response(
            data={"user_id": user_id, "roles": roles},
            status_code=status.HTTP_200_OK,
            message="User roles retrieved successfully"
        )
    except Exception as e:
        logging.error(f"사용자 역할 조회 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve user roles",
            detail={"error": str(e)}
        )


@router.post("/users/{user_id}/assign", summary="사용자에게 역할 할당", dependencies=[Depends(require_admin)])
async def assign_role_to_user(user_id: str, role_data: UserRoleAssign, role_service: RoleService = Depends(get_role_service)):
    """사용자에게 역할을 할당합니다. (관리자 전용)"""
    try:
        user_role = role_service.assign_role_to_user(user_id, role_data.role_name)
        
        if user_role is None:
            return create_response(
                data={"user_id": user_id, "role": role_data.role_name},
                status_code=status.HTTP_200_OK,
                message="Role already assigned to user"
            )
        
        return create_response(
            data={"user_id": user_id, "role": role_data.role_name},
            status_code=status.HTTP_201_CREATED,
            message="Role assigned to user successfully"
        )
    except Exception as e:
        logging.error(f"역할 할당 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to assign role to user",
            detail={"error": str(e)}
        )


@router.delete("/users/{user_id}/roles/{role_name}", summary="사용자에게서 역할 제거", dependencies=[Depends(require_admin)])
async def remove_role_from_user(user_id: str, role_name: str, role_service: RoleService = Depends(get_role_service)):
    """사용자에게서 역할을 제거합니다. (관리자 전용)"""
    try:
        success = role_service.remove_role_from_user(user_id, role_name)
        
        if not success:
            return create_response(
                data={"user_id": user_id, "role": role_name},
                status_code=status.HTTP_404_NOT_FOUND,
                message="Role not assigned to user"
            )
        
        return create_response(
            data={"user_id": user_id, "role": role_name},
            status_code=status.HTTP_200_OK,
            message="Role removed from user successfully"
        )
    except Exception as e:
        logging.error(f"역할 제거 오류: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to remove role from user",
            detail={"error": str(e)}
        )


@router.get("/me", summary="내 역할 조회")
async def get_my_roles(roles: List[str] = Depends(get_user_roles)):
    """현재 로그인한 사용자의 역할 목록을 조회합니다."""
    return create_response(
        data={"roles": roles},
        status_code=status.HTTP_200_OK,
        message="Your roles retrieved successfully"
    )