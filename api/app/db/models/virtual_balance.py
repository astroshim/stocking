from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class VirtualBalance(UUIDMixin, Base):
    """가상 거래 잔고"""
    __tablename__ = 'virtual_balances'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, unique=True, comment='사용자 ID')
    
    # 잔고 정보
    cash_balance = Column(Numeric(20, 2), nullable=False, default=0, comment='현금 잔고')
    available_cash = Column(Numeric(20, 2), nullable=False, default=0, comment='사용 가능한 현금 (주문 대기 중인 금액 제외)')
    invested_amount = Column(Numeric(20, 2), nullable=False, default=0, comment='투자 금액(원가 기준 확정값)')
    
    # 거래 통계
    total_buy_amount = Column(Numeric(20, 2), nullable=False, default=0, comment='총 매수 금액')
    total_sell_amount = Column(Numeric(20, 2), nullable=False, default=0, comment='총 매도 금액')
    total_commission = Column(Numeric(10, 2), nullable=False, default=0, comment='총 수수료')
    total_tax = Column(Numeric(10, 2), nullable=False, default=0, comment='총 세금')
    
    # 시간 정보
    last_trade_date = Column(DateTime, nullable=True, comment='마지막 거래일')
    last_updated_at = Column(DateTime, nullable=False, default=datetime.now, comment='마지막 업데이트 시간')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='virtual_balance')
    balance_histories = relationship('VirtualBalanceHistory', back_populates='virtual_balance', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<VirtualBalance {self.user_id}: Cash {self.cash_balance}>'


class VirtualBalanceHistory(UUIDMixin, Base):
    """가상 거래 잔고 이력"""
    __tablename__ = 'virtual_balance_histories'

    virtual_balance_id = Column(String(36), ForeignKey('virtual_balances.id'), nullable=False, comment='가상 잔고 ID')
    
    # 변경 전후 정보
    previous_cash_balance = Column(Numeric(20, 2), nullable=False, comment='변경 전 현금 잔고')
    new_cash_balance = Column(Numeric(20, 2), nullable=False, comment='변경 후 현금 잔고')
    change_amount = Column(Numeric(20, 2), nullable=False, comment='변경 금액')
    change_type = Column(String(20), nullable=False, comment='변경 유형 (BUY/SELL/DEPOSIT/WITHDRAW)')
    
    # 관련 정보
    related_order_id = Column(String(36), ForeignKey('orders.id'), nullable=True, comment='관련 주문 ID')
    description = Column(Text, nullable=True, comment='변경 설명')
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # 관계 설정
    virtual_balance = relationship('VirtualBalance', back_populates='balance_histories')

    def __repr__(self):
        return f'<VirtualBalanceHistory {self.virtual_balance_id}: {self.change_type} {self.change_amount}>'


