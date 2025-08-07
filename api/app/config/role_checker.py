from typing import List, Optional, Union
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError

from app.config import config
from app.config.get_current_user import get_current_user, api_key_header, ALGORITHM
from app.db.models.role import RoleEnum


def get_user_roles(authorization: Optional[str] = Depends(api_key_header)) -> List[str]:
    """
    JWT 토큰에서 사용자 역할 정보를 추출합니다.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # "Bearer " 프리픽스가 있으면 제거
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        roles = payload.get("roles", [])
        
        # 역할이 없는 경우 기본 역할 부여
        if not roles:
            roles = ["user"]
            
        return roles
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


def has_role(required_roles: Union[str, List[str]]):
    """
    사용자가 필요한 역할을 가지고 있는지 확인하는 의존성 함수를 반환합니다.
    
    Args:
        required_roles: 필요한 역할 또는 역할 목록
        
    Returns:
        사용자 ID (역할 확인 후)
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]
        
    async def role_checker(user_id: str = Depends(get_current_user), roles: List[str] = Depends(get_user_roles)):
        # 관리자는 모든 권한을 가짐
        if "admin" in roles:
            return user_id
            
        # 필요한 역할 중 하나라도 있는지 확인
        for role in required_roles:
            if role in roles:
                return user_id
                
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="권한 오류. 권한이 충분하지 않습니다."
        )
        
    return role_checker


# 역할별 의존성 함수 (편의를 위해 미리 정의)
require_admin = has_role(RoleEnum.ADMIN.value)
require_moderator = has_role([RoleEnum.ADMIN.value, RoleEnum.MODERATOR.value])
require_premium = has_role([RoleEnum.ADMIN.value, RoleEnum.PREMIUM.value])
require_user = has_role([RoleEnum.ADMIN.value, RoleEnum.MODERATOR.value, RoleEnum.USER.value, RoleEnum.PREMIUM.value])