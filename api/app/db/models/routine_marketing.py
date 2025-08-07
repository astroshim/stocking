from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.db.models.uuid_mixin import UUIDMixin
from app.config.db import Base

class RoutineMarketing(UUIDMixin, Base):
    __tablename__ = 'routine_marketing'

    email = Column(String(255), nullable=False, default='')
    country = Column(String(255), nullable=False, default='')
    skin_type = Column(String(255), nullable=False, default='')
    product_name = Column(String(255), nullable=False, default='')
    product_image_url = Column(String(255), nullable=False, default='')
    ip = Column(String(255), nullable=False, default='')
    user_client_info = Column(String(255), nullable=False, default='') 
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now) 