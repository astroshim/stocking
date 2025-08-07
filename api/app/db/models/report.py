from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.models.uuid_mixin import UUIDMixin
from app.config.db import Base


class Report(UUIDMixin, Base):
    __tablename__ = 'reports'

    user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='신고한 사용자')
    reportable_type = Column(String(50), nullable=False, comment='신고 대상 유형(verification, user, etc)')
    reportable_id = Column(CHAR(36), nullable=False, comment='신고 대상 ID')
    reason = Column(String(255), nullable=False, comment='신고 이유')
    description = Column(Text, nullable=True, comment='신고 세부 내용')
    status = Column(String(20), nullable=True, default='pending', comment='처리 상태: pending, in_progress, resolved')
    handled_by = Column(String(36), nullable=True, comment='처리자(운영자) ID')
    handled_at = Column(DateTime, nullable=True, comment='처리 시각')
    # resolution = Column(String(50), nullable=True, comment='처리 결과(accepted/rejected 등)')
    handler_comment = Column(Text, nullable=True, comment='처리자가 남긴 코멘트/메모')
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.now(), onupdate=datetime.now())

    reporter = relationship('User', back_populates='reports')

    # 문자열로 관계 정의
    status_histories = relationship(
        'ReportStatusHistory',
        back_populates='report',
        lazy='dynamic'
    )

    @property
    def last_status_history(self):
        from sqlalchemy import desc
        return self.status_histories.order_by(desc('handled_at')).first()

    def __repr__(self):
        return f'<Report id={self.id}, type={self.reportable_type}, target_id={self.reportable_id}>'
