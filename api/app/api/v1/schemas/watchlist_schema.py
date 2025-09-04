from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel
from app.api.v1.schemas.stock_schemas import StockPriceDetailsResponse


class WatchListBase(BaseModel):
    product_code: str = Field(..., description="상품 코드 (주식, 코인 등)")


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
    product_code: str
    directory_id: Optional[str]
    product_name: str | None = None
    market: str | None = None
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
    stock_price_details: Optional[StockPriceDetailsResponse] = Field(None, description="토스 주가 상세 응답")


class WatchListListResponse(PagedResponse[WatchListWithStockResponse]):
    pass


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
