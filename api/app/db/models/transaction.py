from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Text, Enum as SQLEnum, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class TransactionType(enum.Enum):
    """거래 유형"""
    BUY = "BUY"                   # 매수
    SELL = "SELL"                 # 매도
    DIVIDEND = "DIVIDEND"         # 배당금 수령
    DEPOSIT = "DEPOSIT"           # 입금
    WITHDRAW = "WITHDRAW"         # 출금
    FEE = "FEE"                   # 수수료
    TAX = "TAX"                   # 세금


class Transaction(UUIDMixin, Base):
    """거래 내역"""
    __tablename__ = 'transactions'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    stock_id = Column(String(20), nullable=True, comment='주식 종목 코드 (주식 거래시, 예: 097230)')
    order_id = Column(String(36), ForeignKey('orders.id'), nullable=True, comment='주문 ID (주문 관련 거래시)')
    
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, comment='거래 유형')
    
    # 거래 정보
    quantity = Column(Numeric(20, 0), nullable=True, comment='거래 수량 (주식 거래시)')
    price = Column(Numeric(10, 2), nullable=True, comment='거래가격 (주식 거래시)')
    amount = Column(Numeric(20, 2), nullable=False, comment='거래금액')
    
    # 수수료 및 세금
    commission = Column(Numeric(10, 2), nullable=False, default=0, comment='수수료')
    tax = Column(Numeric(10, 2), nullable=False, default=0, comment='세금')
    net_amount = Column(Numeric(20, 2), nullable=False, comment='순 거래금액 (수수료, 세금 제외)')
    
    # 잔고 변화
    cash_balance_before = Column(Numeric(20, 2), nullable=False, comment='거래 전 현금 잔고')
    cash_balance_after = Column(Numeric(20, 2), nullable=False, comment='거래 후 현금 잔고')
    
    # 시간 정보
    transaction_date = Column(DateTime, nullable=False, default=datetime.now, comment='거래일시')
    settlement_date = Column(DateTime, nullable=True, comment='결제일 (T+2)')
    
    # 기타
    description = Column(Text, nullable=True, comment='거래 설명')
    reference_number = Column(String(50), nullable=True, comment='참조번호')
    is_simulated = Column(Boolean, nullable=False, default=True, comment='가상거래 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='transactions')
    order = relationship('Order', back_populates='transactions')

    def __repr__(self):
        return f'<Transaction {self.id}: {self.transaction_type.value} {self.amount}>'


class TradingStatistics(UUIDMixin, Base):
    """거래 통계"""
    __tablename__ = 'trading_statistics'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    
    # 기간별 통계
    period_type = Column(String(10), nullable=False, comment='기간 유형 (daily/weekly/monthly/yearly)')
    period_start = Column(DateTime, nullable=False, comment='기간 시작일')
    period_end = Column(DateTime, nullable=False, comment='기간 종료일')
    
    # 거래 통계
    total_trades = Column(Numeric(10, 0), nullable=False, default=0, comment='총 거래 횟수')
    buy_trades = Column(Numeric(10, 0), nullable=False, default=0, comment='매수 거래 횟수')
    sell_trades = Column(Numeric(10, 0), nullable=False, default=0, comment='매도 거래 횟수')
    
    # 금액 통계
    total_buy_amount = Column(Numeric(20, 2), nullable=False, default=0, comment='총 매수 금액')
    total_sell_amount = Column(Numeric(20, 2), nullable=False, default=0, comment='총 매도 금액')
    total_commission = Column(Numeric(10, 2), nullable=False, default=0, comment='총 수수료')
    total_tax = Column(Numeric(10, 2), nullable=False, default=0, comment='총 세금')
    
    # 손익 통계
    realized_profit_loss = Column(Numeric(20, 2), nullable=False, default=0, comment='실현 손익')
    win_trades = Column(Numeric(10, 0), nullable=False, default=0, comment='수익 거래 횟수')
    loss_trades = Column(Numeric(10, 0), nullable=False, default=0, comment='손실 거래 횟수')
    win_rate = Column(Numeric(5, 2), nullable=False, default=0, comment='승률 (%)')
    
    # 포트폴리오 가치
    portfolio_value_start = Column(Numeric(20, 2), nullable=False, default=0, comment='기간 시작시 포트폴리오 가치')
    portfolio_value_end = Column(Numeric(20, 2), nullable=False, default=0, comment='기간 종료시 포트폴리오 가치')
    portfolio_return = Column(Numeric(5, 2), nullable=False, default=0, comment='포트폴리오 수익률 (%)')
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='trading_statistics')

    def __repr__(self):
        return f'<TradingStatistics {self.user_id}: {self.period_type} {self.period_start}>'


