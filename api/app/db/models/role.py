from enum import Enum
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class RoleEnum(str, Enum):
    """사용자 역할 정의"""
    ADMIN = "admin"           # 관리자 (모든 권한)
    MODERATOR = "moderator"   # 중재자 (콘텐츠 관리, 신고 처리 등)
    USER = "user"             # 일반 사용자 (기본 권한)
    PREMIUM = "premium"       # 프리미엄 사용자 (추가 기능 접근)
    GUEST = "guest"           # 게스트 (제한된 접근)


class Role(UUIDMixin, Base):
    """역할 모델"""
    __tablename__ = 'roles'
    
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    
    # 관계 정의
    users = relationship("UserRole", back_populates="role")
    
    def __repr__(self):
        return f"<Role {self.name}>"


class UserRole(UUIDMixin, Base):
    """사용자-역할 연결 모델"""
    __tablename__ = 'user_roles'
    
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role_id = Column(String(36), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)

# 관계 정의
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")
    
    def __repr__(self):
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"