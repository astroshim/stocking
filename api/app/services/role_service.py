from typing import List, Optional, Dict, Any
from datetime import datetime

from app.db.models.role import Role, UserRole, RoleEnum
from app.db.repositories.role_repository import RoleRepository, UserRoleRepository
from app.utils.transaction_manager import TransactionManager


class RoleService:
    """역할 관련 비즈니스 로직을 처리하는 서비스"""
    
    def __init__(self, role_repository: RoleRepository, user_role_repository: UserRoleRepository):
        self.role_repository = role_repository
        self.user_role_repository = user_role_repository
    
    def get_role_by_id(self, role_id: str) -> Optional[Role]:
        """ID로 역할 조회"""
        return self.role_repository.get_by_id(role_id)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """이름으로 역할 조회"""
        return self.role_repository.get_by_name(name)
    
    def list_roles(self) -> List[Role]:
        """모든 역할 조회"""
        return self.role_repository.list_roles()
    
    def create_role(self, role_data: Dict[str, Any]) -> Role:
        """새 역할 생성"""
        with TransactionManager.transaction(self.role_repository.session):
            return self.role_repository.create_role(
                name=role_data['name'],
                description=role_data.get('description')
            )
    
    def delete_role(self, role_id: str) -> bool:
        """역할 삭제"""
        with TransactionManager.transaction(self.role_repository.session):
            return self.role_repository.delete_role(role_id)
    
    def assign_role_to_user(self, user_id: str, role_name: str) -> Optional[UserRole]:
        """사용자에게 역할 할당"""
        with TransactionManager.transaction(self.role_repository.session):
            # 역할 이름으로 역할 조회
            role = self.role_repository.get_by_name(role_name)
            if not role:
                # 역할이 없으면 생성 (선택적)
                role = self.role_repository.create_role(name=role_name)
            
            # 이미 할당되어 있는지 확인
            if self.user_role_repository.has_role(user_id, role_name):
                return None  # 이미 할당됨
            
            # 역할 할당
            return self.user_role_repository.assign_role_to_user(user_id, role.id)
    
    def remove_role_from_user(self, user_id: str, role_name: str) -> bool:
        """사용자에게서 역할 제거"""
        with TransactionManager.transaction(self.role_repository.session):
            # 역할 이름으로 역할 조회
            role = self.role_repository.get_by_name(role_name)
            if not role:
                return False  # 역할이 없음
            
            # 역할 제거
            return self.user_role_repository.remove_role_from_user(user_id, role.id)
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """사용자의 모든 역할 이름 조회"""
        return self.user_role_repository.get_user_role_names(user_id)
    
    def has_role(self, user_id: str, role_name: str) -> bool:
        """사용자가 특정 역할을 가지고 있는지 확인"""
        return self.user_role_repository.has_role(user_id, role_name)
    
    def initialize_default_roles(self) -> None:
        """기본 역할 초기화 (애플리케이션 시작 시 호출)"""
        with TransactionManager.transaction(self.role_repository.session):
            # 기본 역할 생성
            for role_enum in RoleEnum:
                role = self.role_repository.get_by_name(role_enum.value)
                if not role:
                    description = f"{role_enum.value.capitalize()} role"
                    self.role_repository.create_role(name=role_enum.value, description=description)