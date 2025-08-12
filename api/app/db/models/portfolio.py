from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class Portfolio(UUIDMixin, Base):
    """사용자 포트폴리오 (보유 주식)"""
    __tablename__ = 'portfolios'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    stock_id = Column(String(20), nullable=False, comment='주식 종목 코드 (예: 097230)')
    
    # 보유 수량 및 가격 정보
    current_quantity = Column(Numeric(20, 0), nullable=False, default=0, comment='현재 보유 수량')
    average_price = Column(Numeric(10, 2), nullable=False, comment='평균 매수가')
    
    # 손익 정보 (확정값만 저장)
    realized_profit_loss = Column(Numeric(20, 2), nullable=False, default=0, comment='실현 손익')
    
    # 시간 정보
    first_buy_date = Column(DateTime, nullable=False, comment='최초 매수일')
    last_buy_date = Column(DateTime, nullable=True, comment='최근 매수일')
    last_sell_date = Column(DateTime, nullable=True, comment='최근 매도일')
    last_updated_at = Column(DateTime, nullable=False, default=datetime.now, comment='마지막 업데이트 시간')
    
    # 기타
    is_active = Column(Boolean, nullable=False, default=True, comment='활성 보유 여부')
    notes = Column(Text, nullable=True, comment='포트폴리오 메모')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='portfolios')

    def __repr__(self):
        return f'<Portfolio {self.user_id}: {self.current_quantity} shares of {self.stock_id}>'

