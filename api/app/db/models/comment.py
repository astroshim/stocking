from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class Comment(UUIDMixin, Base):
    __tablename__ = 'comments'

    user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=True, comment='작성자 ID')
    commentable_id = Column(CHAR(36), nullable=False, comment='코멘트 대상 ID')
    commentable_type = Column(String(255), nullable=False, comment='코멘트 대상 타입')

    content = Column(Text, nullable=False, comment='코멘트 내용')
    ancestry = Column(String(255), nullable=True, comment='계층 구조 경로')
    ancestry_depth = Column(Integer, default=0, comment='계층 깊이 캐시')
    children_count = Column(Integer, default=0, comment='하위 코멘트 수 캐시')
    is_question = Column(Boolean, default=True, comment='질문이면 True, 답변이면 False')
    answer_name = Column(String(255), default="", comment='답변한 사람, card package 주인 혹은 system 관리자(CS)')

    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.now(), onupdate=datetime.now())

    # 관계 설정
    user = relationship('User', back_populates='comments')
