from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel
from app.db.models.order import OrderType, OrderMethod, OrderStatus


class PortfolioResponse(InitVarModel):
    id: str
    user_id: str
    product_code: str
    product_name: str
    market: str
    industry_code: Optional[str] = Field(None, description="업종 코드")
    industry_display: Optional[str] = Field(None, description="업종명")
    quantity: Decimal
    average_buy_price: Decimal
    total_buy_amount: Decimal
    current_value: Optional[Decimal]
    # unrealized_profit_loss: Optional[Decimal]
    # unrealized_profit_loss_rate: Optional[Decimal]
    first_buy_date: datetime
    last_buy_date: Optional[datetime]
    last_sell_date: Optional[datetime]
    last_updated_at: datetime
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    average_exchange_rate: Optional[Decimal] = Field(None, description="평균 매수 시점 환율 (외화 -> KRW)")
    krw_average_price: Optional[Decimal] = Field(None, description="원화 환산 평균 매수가")
    
    # 손익 정보
    realized_profit_loss: Optional[Decimal] = Field(None, description="누적 실현 손익 (현지통화)")
    krw_realized_profit_loss: Optional[Decimal] = Field(None, description="원화 환산 누적 실현 손익")
    realized_profit_loss_rate: Optional[Decimal] = Field(None, description="누적 실현 손익률 (%) - KRW 기준")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "id": "1234567890abcdef1234567890abcdef",
            "user_id": "user123",
            "product_code": "AAPL",
            "product_name": "Apple Inc.",
            "market": "NASDAQ",
            "industry_code": "TECH_SEMICONDUCTOR",
            "industry_display": "반도체",
            "quantity": 10,
            "average_buy_price": 150.00,
            "total_buy_amount": 1500.00,
            "current_value": 160.00,
            "first_buy_date": "2023-01-01T10:00:00Z",
            "last_buy_date": "2023-01-05T10:00:00Z",
            "last_sell_date": None,
            "last_updated_at": "2023-01-10T10:00:00Z",
            "is_active": True,
            "notes": "Some notes",
            "created_at": "2023-01-01T10:00:00Z",
            "updated_at": "2023-01-10T10:00:00Z",
            "average_exchange_rate": 1200.00,
            "krw_average_price": 180000.00,
            "realized_profit_loss": 100.00,
            "krw_realized_profit_loss": 120000.00
            ,
            "realized_profit_loss_rate": 12.34
        }


class PortfolioWithStockResponse(PortfolioResponse):
    current_price: Optional[Decimal] = Field(None, description="현재가")
    orders: List['OrderBriefInPortfolio'] = Field(default_factory=list, description="해당 포트폴리오의 주문 목록")


class OrderBriefInPortfolio(InitVarModel):
    id: str
    order_type: OrderType
    order_method: OrderMethod
    order_status: OrderStatus
    quantity: Decimal
    order_price: Optional[Decimal]
    currency: str
    exchange_rate: Optional[Decimal]
    created_at: datetime


class PortfolioListResponse(PagedResponse[PortfolioWithStockResponse]):
    pass


class PortfolioSummaryResponse(BaseModel):
    total_stocks: int = Field(..., description="보유 종목 수")
    total_invested_amount: Decimal = Field(..., description="총 투자 금액 (현지통화 합계)")
    total_invested_amount_krw: Optional[Decimal] = Field(None, description="총 투자 금액 (KRW 환산 합계)")
    total_current_value: Decimal = Field(..., description="총 현재 가치 (현지통화 합계 - 임시)")
    total_current_value_krw: Optional[Decimal] = Field(None, description="총 현재 가치 (KRW 환산 합계 - 임시)")
    total_profit_loss: Decimal = Field(..., description="총 손익 (KRW 기준)")
    total_profit_loss_rate: Decimal = Field(..., description="총 손익률 (KRW 기준)")
    best_stock: Optional[str] = Field(None, description="최고 수익 종목")
    worst_stock: Optional[str] = Field(None, description="최저 수익 종목")


class PortfolioAnalysisResponse(BaseModel):
    """포트폴리오 분석 결과"""
    sector_allocation: List[dict] = Field(..., description="섹터별 배분")
    top_holdings: List[dict] = Field(..., description="상위 보유 종목")
    performance_metrics: dict = Field(..., description="성과 지표")
    risk_metrics: dict = Field(..., description="리스크 지표")


class PortfolioDashboardResponse(BaseModel):
    """포트폴리오 대시보드 응답"""
    total_invested_amount: Decimal = Field(..., description="원금 (투자금액)")
    total_current_value: Decimal = Field(..., description="현재 총 평가금액")
    total_profit_loss: Decimal = Field(..., description="총 수익금 (평가금 - 원금)")
    total_profit_loss_rate: Decimal = Field(..., description="총 수익률 (%)")
    daily_profit_loss: Decimal = Field(..., description="일간 손익금")
    daily_profit_loss_rate: Decimal = Field(..., description="일간 손익률 (%)")