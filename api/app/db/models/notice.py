from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class Notice(UUIDMixin, Base):
    __tablename__ = 'notices'

    creator_id = Column(CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='생성자 ID')
    title = Column(String(255), nullable=False, comment='제목')
    content = Column(Text, nullable=False, comment='내용')
    is_active = Column(Boolean, nullable=False, default=True, comment='활성화 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.now(), onupdate=datetime.now())

    # 공지사항 creator
    creator = relationship('User', foreign_keys=[creator_id], back_populates='notices')

    def __repr__(self):
        return f'<Notice {self.title}>'