from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import CHAR
from datetime import datetime

from app.db.models.uuid_mixin import UUIDMixin
from app.config.db import Base


class WatchlistDirectory(UUIDMixin, Base):
    """관심종목 디렉토리"""
    __tablename__ = 'watchlist_directories'

    # UUIDMixin의 id 컬럼을 오버라이드하여 CHAR(41)로 확장
    id = Column(CHAR(41), primary_key=True)

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    name = Column(String(50), nullable=False, comment='디렉토리 이름')
    description = Column(Text, nullable=True, comment='디렉토리 설명')
    
    # 순서 및 설정
    display_order = Column(Integer, nullable=False, default=0, comment='표시 순서')
    color = Column(String(20), nullable=True, comment='디렉토리 색상 (hex code)')
    
    is_active = Column(Boolean, nullable=False, default=True, comment='활성 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User')
    watch_lists = relationship('WatchList', back_populates='directory')

    def __repr__(self):
        return f'<WatchlistDirectory {self.user_id}: {self.name}>'


class WatchList(UUIDMixin, Base):
    """관심 종목"""
    __tablename__ = 'watch_lists'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    directory_id = Column(String(41), ForeignKey('watchlist_directories.id'), nullable=True, comment='디렉토리 ID')
    stock_id = Column(String(20), nullable=False, comment='주식 종목 코드 (예: 097230)')
    
    # 관심 종목 정보
    add_date = Column(DateTime, nullable=False, default=datetime.now, comment='추가일')
    target_price = Column(Numeric(10, 2), nullable=True, comment='목표가')
    stop_loss_price = Column(Numeric(10, 2), nullable=True, comment='손절가')
    memo = Column(Text, nullable=True, comment='메모')
    
    # 알림 설정
    price_alert_enabled = Column(Boolean, nullable=False, default=False, comment='가격 알림 활성화')
    price_alert_upper = Column(Numeric(10, 2), nullable=True, comment='상한 알림가')
    price_alert_lower = Column(Numeric(10, 2), nullable=True, comment='하한 알림가')
    volume_alert_enabled = Column(Boolean, nullable=False, default=False, comment='거래량 알림 활성화')
    volume_alert_threshold = Column(Numeric(20, 0), nullable=True, comment='거래량 알림 기준')
    
    # 순서 및 카테고리 (하위 호환성을 위해 category 유지)
    display_order = Column(Integer, nullable=False, default=0, comment='표시 순서')
    category = Column(String(50), nullable=True, comment='카테고리 (구버전 호환)')
    
    is_active = Column(Boolean, nullable=False, default=True, comment='활성 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='watch_lists')
    directory = relationship('WatchlistDirectory', back_populates='watch_lists')

    def __repr__(self):
        return f'<WatchList {self.user_id}: {self.stock_id}>'
