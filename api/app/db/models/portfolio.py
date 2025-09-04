from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class ProductType(Enum):
    """자산 유형"""
    STOCK = "STOCK"  # 주식
    CRYPTO = "CRYPTO"  # 암호화폐


class Portfolio(UUIDMixin, Base):
    """사용자 포트폴리오 (보유 자산: 주식/코인)"""
    __tablename__ = 'portfolios'

    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, comment='사용자 ID')
    
    # 상품 기본 정보
    product_code = Column(String(20), nullable=False, comment='상품 코드 (주식: A005930, 코인: BTC-KRW)')
    product_name = Column(String(100), nullable=False, comment='상품명 (삼성전자, 비트코인)')
    product_type = Column(SQLEnum(ProductType), nullable=False, comment='자산 유형 (STOCK/CRYPTO)')
    
    # 시장/거래소 정보
    market = Column(String(50), nullable=False, comment='시장/거래소 (KOSPI, NASDAQ, Upbit, Binance)')
    
    # 코인 특화 정보 (주식의 경우 NULL)
    symbol = Column(String(10), nullable=True, comment='코인 심볼 (BTC, ETH, ADA)')
    base_currency = Column(String(10), nullable=True, comment='기준 통화 (KRW, USDT, USD)')
    
    # 보유 수량 및 가격 정보
    current_quantity = Column(Numeric(20, 8), nullable=False, default=0, comment='현재 보유 수량 (코인: 소수점 8자리)')
    average_price = Column(Numeric(20, 8), nullable=False, comment='평균 매수가 (현지통화 기준)')
    
    # 환율 정보 (해외자산용)
    average_exchange_rate = Column(Numeric(10, 4), nullable=True, comment='평균 매수 시점 환율 (외화 -> KRW)')
    krw_average_price = Column(Numeric(20, 2), nullable=True, comment='원화 환산 평균 매수가')
    
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
    orders = relationship('Order', back_populates='portfolio', passive_deletes=True)

    def __repr__(self):
        asset_type = "shares" if self.product_type == ProductType.STOCK else "units"
        return f'<Portfolio {self.user_id}: {self.current_quantity} {asset_type} of {self.product_name} ({self.product_code})>'

