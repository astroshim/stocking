from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class StockBase(BaseModel):
    code: str = Field(..., description="주식 종목 코드")
    name: str = Field(..., description="주식 종목명")
    market: str = Field(..., description="시장 구분")


class StockCreate(StockBase):
    sector: Optional[str] = Field(None, description="업종")
    industry: Optional[str] = Field(None, description="세부 업종")
    market_cap: Optional[Decimal] = Field(None, description="시가총액")
    listed_shares: Optional[Decimal] = Field(None, description="상장 주식 수")
    listing_date: Optional[datetime] = Field(None, description="상장일")
    description: Optional[str] = Field(None, description="종목 설명")


class StockUpdate(BaseModel):
    name: Optional[str] = Field(None, description="주식 종목명")
    sector: Optional[str] = Field(None, description="업종")
    industry: Optional[str] = Field(None, description="세부 업종")
    market_cap: Optional[Decimal] = Field(None, description="시가총액")
    listed_shares: Optional[Decimal] = Field(None, description="상장 주식 수")
    description: Optional[str] = Field(None, description="종목 설명")
    is_active: Optional[bool] = Field(None, description="거래 활성화 여부")


class StockResponse(InitVarModel):
    id: str
    code: str
    name: str
    market: str
    sector: Optional[str]
    industry: Optional[str]
    market_cap: Optional[Decimal]
    listed_shares: Optional[Decimal]
    is_active: bool
    listing_date: Optional[datetime]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class StockPriceBase(BaseModel):
    open_price: Decimal = Field(..., description="시가")
    high_price: Decimal = Field(..., description="고가")
    low_price: Decimal = Field(..., description="저가")
    close_price: Decimal = Field(..., description="종가")
    current_price: Decimal = Field(..., description="현재가")
    volume: Decimal = Field(default=0, description="거래량")
    trading_value: Decimal = Field(default=0, description="거래대금")


class StockPriceCreate(StockPriceBase):
    stock_id: str = Field(..., description="주식 종목 ID")
    price_change: Decimal = Field(default=0, description="전일 대비 가격 변동")
    price_change_rate: Decimal = Field(default=0, description="전일 대비 변동률")
    price_date: datetime = Field(..., description="가격 기준일시")
    is_real_time: bool = Field(default=True, description="실시간 데이터 여부")


class StockPriceResponse(InitVarModel):
    id: str
    stock_id: str
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    current_price: Decimal
    volume: Decimal
    trading_value: Decimal
    price_change: Decimal
    price_change_rate: Decimal
    price_date: datetime
    is_real_time: bool
    created_at: datetime


class StockWithPriceResponse(StockResponse):
    current_price: Optional[StockPriceResponse] = Field(None, description="현재 가격 정보")


class StockListResponse(PagedResponse[StockWithPriceResponse]):
    pass


class StockSearchRequest(BaseModel):
    keyword: Optional[str] = Field(None, description="검색 키워드 (종목명 또는 코드)")
    market: Optional[str] = Field(None, description="시장 구분")
    sector: Optional[str] = Field(None, description="업종")
    is_active: Optional[bool] = Field(None, description="거래 활성화 여부")