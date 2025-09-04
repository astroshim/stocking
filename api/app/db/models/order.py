from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Numeric, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class OrderType(enum.Enum):
    """주문 유형"""
    BUY = "BUY"           # 매수
    SELL = "SELL"         # 매도


class OrderMethod(enum.Enum):
    """주문 방식"""
    MARKET = "MARKET"     # 시장가
    LIMIT = "LIMIT"       # 지정가


class OrderStatus(enum.Enum):
    """주문 상태"""
    PENDING = "PENDING"           # 대기중
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 부분체결
    FILLED = "FILLED"             # 체결완료
    CANCELLED = "CANCELLED"       # 취소됨
    REJECTED = "REJECTED"         # 거부됨
    EXPIRED = "EXPIRED"           # 만료됨


class ExitReason(enum.Enum):
    """매도 사유 (SELL 주문에 한해 기록)"""
    STOP_LOSS = "STOP_LOSS"       # 손절매
    TAKE_PROFIT = "TAKE_PROFIT"   # 이익실현


class Order(UUIDMixin, Base):
    """주식/코인 주문 정보 (글로벌 지원)"""
    __tablename__ = 'orders'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    portfolio_id = Column(String(36), ForeignKey('portfolios.id', ondelete='SET NULL'), nullable=True, index=True, comment='연결된 포트폴리오 ID')
    
    # 상품 정보 (Portfolio와 동일한 구조)
    product_code = Column(String(20), nullable=False, comment='상품 코드 (주식: 005930, 해외주식: AAPL, 코인: BTC-KRW)')
    product_name = Column(String(100), nullable=False, comment='상품명 (삼성전자, Apple Inc., 비트코인)')
    market = Column(String(50), nullable=False, comment='시장/거래소 (KOSPI, NYSE, NASDAQ, Upbit)')
    
    # 주문 기본 정보
    order_type = Column(SQLEnum(OrderType), nullable=False, comment='주문 유형 (BUY/SELL)')
    order_method = Column(SQLEnum(OrderMethod), nullable=False, comment='주문 방식 (MARKET/LIMIT)')
    order_status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, comment='주문 상태')
    
    # 주문 수량 및 가격 (소수점 8자리 지원)
    quantity = Column(Numeric(20, 8), nullable=False, comment='주문 수량 (코인: 소수점 8자리)')
    order_price = Column(Numeric(20, 8), nullable=True, comment='주문 가격 (원화 또는 현지통화)')
    executed_quantity = Column(Numeric(20, 8), nullable=False, default=0, comment='체결된 수량')
    executed_amount = Column(Numeric(20, 8), nullable=False, default=0, comment='체결된 금액 (현지통화)')
    average_price = Column(Numeric(20, 8), nullable=True, comment='평균 체결가 (현지통화)')
    
    # 환율 정보 (해외주식/코인용)
    currency = Column(String(10), nullable=False, default='KRW', comment='주문 통화 (KRW/USD/EUR/JPY)')
    exchange_rate = Column(Numeric(10, 4), nullable=True, comment='거래 시점 환율 (외화 -> KRW)')
    krw_order_price = Column(Numeric(20, 2), nullable=True, comment='원화 환산 주문가격')
    krw_executed_amount = Column(Numeric(20, 2), nullable=True, comment='원화 환산 체결금액')
    
    # 수수료 및 세금
    commission = Column(Numeric(10, 2), nullable=False, default=0, comment='거래 수수료')
    tax = Column(Numeric(10, 2), nullable=False, default=0, comment='거래세')
    total_fee = Column(Numeric(10, 2), nullable=False, default=0, comment='총 수수료')
    
    # 시간 정보
    order_date = Column(DateTime, nullable=False, default=datetime.now, comment='주문일시')
    executed_date = Column(DateTime, nullable=True, comment='체결일시')
    cancelled_date = Column(DateTime, nullable=True, comment='취소일시')
    expires_at = Column(DateTime, nullable=True, comment='주문 만료일시')
    
    # 기타 정보
    notes = Column(Text, nullable=True, comment='주문 메모')
    exit_reason = Column(SQLEnum(ExitReason), nullable=True, comment='매도 사유 (SELL 주문시: STOP_LOSS/TAKE_PROFIT)')
    is_simulated = Column(Boolean, nullable=False, default=True, comment='가상거래 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    user = relationship('User', back_populates='orders')
    portfolio = relationship('Portfolio', back_populates='orders')
    order_executions = relationship('OrderExecution', back_populates='order', cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='order', cascade='all, delete-orphan')

    def __repr__(self):
        asset_type = "shares" if self.currency == 'KRW' else "units"
        return f'<Order {self.id}: {self.order_type.value} {self.quantity} {asset_type} of {self.product_name} ({self.product_code})>'


class OrderExecution(UUIDMixin, Base):
    """주문 체결 내역 (부분 체결 추적용)"""
    __tablename__ = 'order_executions'

    order_id = Column(String(36), ForeignKey('orders.id'), nullable=False, comment='주문 ID')
    execution_price = Column(Numeric(20, 8), nullable=False, comment='체결가격 (현지통화)')
    execution_quantity = Column(Numeric(20, 8), nullable=False, comment='체결수량')
    execution_amount = Column(Numeric(20, 8), nullable=False, comment='체결금액 (현지통화)')
    execution_time = Column(DateTime, nullable=False, default=datetime.now, comment='체결시간')
    execution_fee = Column(Numeric(20, 8), nullable=False, default=0, comment='체결 수수료')
    
    # 환율 정보 (체결 시점 기준)
    exchange_rate = Column(Numeric(10, 4), nullable=True, comment='체결 시점 환율 (외화 -> KRW)')
    krw_execution_price = Column(Numeric(20, 2), nullable=True, comment='원화 환산 체결가격')
    krw_execution_amount = Column(Numeric(20, 2), nullable=True, comment='원화 환산 체결금액')
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # 관계 설정
    order = relationship('Order', back_populates='order_executions')

    def __repr__(self):
        return f'<OrderExecution {self.order_id}: {self.execution_quantity} @ {self.execution_price} ({self.krw_execution_price} KRW)>'