from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class BalanceChangeTypeEnum(str, Enum):
    """잔고 변경 유형"""
    DEPOSIT = "DEPOSIT"           # 입금
    WITHDRAW = "WITHDRAW"         # 출금
    BUY = "BUY"                   # 매수 (거래 시 자동 생성)
    SELL = "SELL"                 # 매도 (거래 시 자동 생성)
    INITIAL_DEPOSIT = "INITIAL_DEPOSIT"  # 초기 잔고 생성 (자동)


class PortfolioResponse(InitVarModel):
    id: str
    user_id: str
    stock_id: str
    quantity: Decimal
    average_buy_price: Decimal
    total_buy_amount: Decimal
    current_value: Optional[Decimal]
    unrealized_profit_loss: Optional[Decimal]
    unrealized_profit_loss_rate: Optional[Decimal]
    realized_profit_loss: Decimal
    first_buy_date: datetime
    last_buy_date: Optional[datetime]
    last_sell_date: Optional[datetime]
    last_updated_at: datetime
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class PortfolioWithStockResponse(PortfolioResponse):
    stock_name: Optional[str] = Field(None, description="주식 종목명")
    current_price: Optional[Decimal] = Field(None, description="현재가")


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


class VirtualBalanceResponse(InitVarModel):
    id: str
    user_id: str
    cash_balance: Decimal
    available_cash: Decimal
    invested_amount: Decimal
    total_buy_amount: Decimal
    total_sell_amount: Decimal
    total_commission: Decimal
    total_tax: Decimal
    last_trade_date: Optional[datetime]
    last_updated_at: datetime
    created_at: datetime
    updated_at: datetime


class VirtualBalanceHistoryResponse(InitVarModel):
    id: str
    virtual_balance_id: str
    previous_cash_balance: Decimal
    new_cash_balance: Decimal
    change_amount: Decimal
    change_type: BalanceChangeTypeEnum
    related_order_id: Optional[str]
    description: Optional[str]
    created_at: datetime


class BalanceUpdateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="변경 금액 (양수만 가능)")
    change_type: BalanceChangeTypeEnum = Field(..., description="변경 유형 (DEPOSIT: 입금, WITHDRAW: 출금)")
    description: Optional[str] = Field(None, description="변경 설명")


class PortfolioAnalysisResponse(BaseModel):
    """포트폴리오 분석 결과"""
    sector_allocation: List[dict] = Field(..., description="섹터별 배분")
    top_holdings: List[dict] = Field(..., description="상위 보유 종목")
    performance_metrics: dict = Field(..., description="성과 지표")
    risk_metrics: dict = Field(..., description="리스크 지표")


class WatchListBase(BaseModel):
    stock_id: str = Field(..., description="주식 종목 ID")


class WatchListCreate(WatchListBase):
    directory_id: Optional[str] = Field(None, description="디렉토리 ID")
    target_price: Optional[Decimal] = Field(None, description="목표가")
    stop_loss_price: Optional[Decimal] = Field(None, description="손절가")
    memo: Optional[str] = Field(None, description="메모")
    price_alert_enabled: bool = Field(default=False, description="가격 알림 활성화")
    price_alert_upper: Optional[Decimal] = Field(None, description="상한 알림가")
    price_alert_lower: Optional[Decimal] = Field(None, description="하한 알림가")
    volume_alert_enabled: bool = Field(default=False, description="거래량 알림 활성화")
    volume_alert_threshold: Optional[Decimal] = Field(None, description="거래량 알림 기준")
    category: Optional[str] = Field(None, description="카테고리 (구버전 호환)")


class WatchListUpdate(BaseModel):
    target_price: Optional[Decimal] = Field(None, description="목표가")
    stop_loss_price: Optional[Decimal] = Field(None, description="손절가")
    memo: Optional[str] = Field(None, description="메모")
    price_alert_enabled: Optional[bool] = Field(None, description="가격 알림 활성화")
    price_alert_upper: Optional[Decimal] = Field(None, description="상한 알림가")
    price_alert_lower: Optional[Decimal] = Field(None, description="하한 알림가")
    volume_alert_enabled: Optional[bool] = Field(None, description="거래량 알림 활성화")
    volume_alert_threshold: Optional[Decimal] = Field(None, description="거래량 알림 기준")
    category: Optional[str] = Field(None, description="카테고리")
    display_order: Optional[int] = Field(None, description="표시 순서")


class WatchListResponse(InitVarModel):
    id: str
    user_id: str
    stock_id: str
    directory_id: Optional[str]
    add_date: datetime
    target_price: Optional[Decimal]
    stop_loss_price: Optional[Decimal]
    memo: Optional[str]
    price_alert_enabled: bool
    price_alert_upper: Optional[Decimal]
    price_alert_lower: Optional[Decimal]
    volume_alert_enabled: bool
    volume_alert_threshold: Optional[Decimal]
    display_order: int
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WatchListWithStockResponse(WatchListResponse):
    stock_name: Optional[str] = Field(None, description="주식 종목명")
    current_price: Optional[Decimal] = Field(None, description="현재가")
    price_change: Optional[Decimal] = Field(None, description="가격 변동")
    price_change_rate: Optional[Decimal] = Field(None, description="변동률")


class WatchListListResponse(PagedResponse[WatchListWithStockResponse]):
    pass


# 관심종목 디렉토리 관련 스키마
class WatchlistDirectoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="디렉토리 이름")


class WatchlistDirectoryCreate(WatchlistDirectoryBase):
    description: Optional[str] = Field(None, max_length=200, description="디렉토리 설명")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="디렉토리 색상 (hex code)")


class WatchlistDirectoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="디렉토리 이름")
    description: Optional[str] = Field(None, max_length=200, description="디렉토리 설명")
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="디렉토리 색상 (hex code)")
    display_order: Optional[int] = Field(None, description="표시 순서")


class WatchlistDirectoryResponse(InitVarModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    display_order: int
    color: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WatchlistDirectoryWithStatsResponse(WatchlistDirectoryResponse):
    watchlist_count: int = Field(..., description="디렉토리 내 관심종목 개수")


class WatchlistDirectoryListResponse(PagedResponse[WatchlistDirectoryWithStatsResponse]):
    pass


class WatchlistDirectoryDetailResponse(WatchlistDirectoryResponse):
    watch_lists: List[WatchListWithStockResponse] = Field(default_factory=list, description="디렉토리 내 관심종목 목록")