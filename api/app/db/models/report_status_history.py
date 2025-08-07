from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.models.uuid_mixin import UUIDMixin
from app.config.db import Base


class ReportStatusHistory(UUIDMixin, Base):
    __tablename__ = 'report_status_histories'

    report_id = Column(String(36), ForeignKey('reports.id'), nullable=False)
    status = Column(String(20), nullable=False)
    # resolution = Column(String(50), nullable=True)
    handled_by = Column(String(36), nullable=False)
    handler_comment = Column(Text, nullable=True)
    handled_at = Column(DateTime(timezone=True), nullable=False)

    report = relationship('Report', back_populates='status_histories')
