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
    quantity: Decimal
    average_buy_price: Decimal
    total_buy_amount: Decimal
    current_value: Optional[Decimal]
    unrealized_profit_loss: Optional[Decimal]
    unrealized_profit_loss_rate: Optional[Decimal]
    first_buy_date: datetime
    last_buy_date: Optional[datetime]
    last_sell_date: Optional[datetime]
    last_updated_at: datetime
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


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
    total_invested_amount: Decimal = Field(..., description="총 투자 금액")
    total_current_value: Decimal = Field(..., description="총 현재 가치")
    total_profit_loss: Decimal = Field(..., description="총 손익")
    total_profit_loss_rate: Decimal = Field(..., description="총 손익률")
    best_stock: Optional[str] = Field(None, description="최고 수익 종목")
    worst_stock: Optional[str] = Field(None, description="최저 수익 종목")


class PortfolioAnalysisResponse(BaseModel):
    """포트폴리오 분석 결과"""
    sector_allocation: List[dict] = Field(..., description="섹터별 배분")
    top_holdings: List[dict] = Field(..., description="상위 보유 종목")
    performance_metrics: dict = Field(..., description="성과 지표")
    risk_metrics: dict = Field(..., description="리스크 지표")