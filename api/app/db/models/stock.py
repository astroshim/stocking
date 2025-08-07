from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class Stock(UUIDMixin, Base):
    """주식 종목 정보"""
    __tablename__ = 'stocks'

    code = Column(String(20), nullable=False, unique=True, comment='주식 종목 코드 (예: 005930)')
    name = Column(String(100), nullable=False, comment='주식 종목명 (예: 삼성전자)')
    market = Column(String(20), nullable=False, comment='시장 구분 (KOSPI, KOSDAQ, NASDAQ 등)')
    sector = Column(String(50), nullable=True, comment='업종')
    industry = Column(String(100), nullable=True, comment='세부 업종')
    market_cap = Column(Numeric(20, 2), nullable=True, comment='시가총액')
    listed_shares = Column(Numeric(20, 0), nullable=True, comment='상장 주식 수')
    is_active = Column(Boolean, nullable=False, default=True, comment='거래 활성화 여부')
    listing_date = Column(DateTime, nullable=True, comment='상장일')
    description = Column(Text, nullable=True, comment='종목 설명')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    # 관계 설정
    stock_prices = relationship('StockPrice', back_populates='stock', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Stock {self.code}: {self.name}>'


class StockPrice(UUIDMixin, Base):
    """주식 가격 정보 (실시간 및 히스토리)"""
    __tablename__ = 'stock_prices'

    stock_id = Column(String(36), ForeignKey('stocks.id'), nullable=False, comment='주식 종목 ID')
    open_price = Column(Numeric(10, 2), nullable=False, comment='시가')
    high_price = Column(Numeric(10, 2), nullable=False, comment='고가')
    low_price = Column(Numeric(10, 2), nullable=False, comment='저가')
    close_price = Column(Numeric(10, 2), nullable=False, comment='종가')
    current_price = Column(Numeric(10, 2), nullable=False, comment='현재가')
    volume = Column(Numeric(20, 0), nullable=False, default=0, comment='거래량')
    trading_value = Column(Numeric(20, 2), nullable=False, default=0, comment='거래대금')
    price_change = Column(Numeric(10, 2), nullable=False, default=0, comment='전일 대비 가격 변동')
    price_change_rate = Column(Numeric(5, 2), nullable=False, default=0, comment='전일 대비 변동률 (%)')
    price_date = Column(DateTime, nullable=False, comment='가격 기준일시')
    is_real_time = Column(Boolean, nullable=False, default=True, comment='실시간 데이터 여부')
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # 관계 설정
    stock = relationship('Stock', back_populates='stock_prices')

    def __repr__(self):
        return f'<StockPrice {self.stock_id}: {self.current_price} at {self.price_date}>'