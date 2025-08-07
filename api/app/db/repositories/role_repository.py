from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.role import Role, UserRole, RoleEnum
from app.db.repositories.base_repository import BaseRepository


class RoleRepository(BaseRepository):
    """역할 관련 데이터베이스 작업을 처리하는 리포지토리"""
    
    def __init__(self, session: Session):
        super().__init__(session)
    
    def get_by_id(self, id: str) -> Optional[Role]:
        """ID로 역할 조회"""
        return self.session.query(Role).filter_by(id=id).first()
    
    def get_by_name(self, name: str) -> Optional[Role]:
        """이름으로 역할 조회"""
        return self.session.query(Role).filter_by(name=name).first()
    
    def list_roles(self) -> List[Role]:
        """모든 역할 조회"""
        return self.session.query(Role).all()
    
    def create_role(self, name: str, description: str = None) -> Role:
        """새 역할 생성"""
        role = Role(name=name, description=description)
        self.add(role)
        return role
    
    def delete_role(self, role_id: str) -> bool:
        """역할 삭제"""
        role = self.get_by_id(role_id)
        if role:
            self.delete(role)
            return True
        return False


class UserRoleRepository(BaseRepository):
    """사용자-역할 연결 관련 데이터베이스 작업을 처리하는 리포지토리"""
    
    def __init__(self, session: Session):
        super().__init__(session)
    
    def get_user_roles(self, user_id: str) -> List[UserRole]:
        """사용자의 모든 역할 연결 조회"""
        return self.session.query(UserRole).filter_by(user_id=user_id).all()
    
    def get_role_users(self, role_id: str) -> List[UserRole]:
        """특정 역할을 가진 모든 사용자 연결 조회"""
        return self.session.query(UserRole).filter_by(role_id=role_id).all()
    
    def assign_role_to_user(self, user_id: str, role_id: str) -> UserRole:
        """사용자에게 역할 할당"""
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.add(user_role)
        return user_role
    
    def remove_role_from_user(self, user_id: str, role_id: str) -> bool:
        """사용자에게서 역할 제거"""
        user_role = self.session.query(UserRole).filter_by(
            user_id=user_id, role_id=role_id
        ).first()
        
        if user_role:
            self.delete(user_role)
            return True
        return False
    
    def has_role(self, user_id: str, role_name: str) -> bool:
        """사용자가 특정 역할을 가지고 있는지 확인"""
        # 역할 이름으로 역할 ID 조회
        role = self.session.query(Role).filter_by(name=role_name).first()
        if not role:
            return False
        
        # 사용자-역할 연결 조회
        user_role = self.session.query(UserRole).filter_by(
            user_id=user_id, role_id=role.id
        ).first()
        
        return user_role is not None
    
    def get_user_role_names(self, user_id: str) -> List[str]:
        """사용자의 모든 역할 이름 조회"""
        user_roles = self.session.query(UserRole).filter_by(user_id=user_id).all()
        role_ids = [ur.role_id for ur in user_roles]
        
        if not role_ids:
            return []
        
        roles = self.session.query(Role).filter(Role.id.in_(role_ids)).all()
        return [role.name for role in roles]