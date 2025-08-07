from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class OrderTypeEnum(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderMethodEnum(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderBase(BaseModel):
    stock_id: str = Field(..., description="주식 종목 ID")
    order_type: OrderTypeEnum = Field(..., description="주문 유형")
    order_method: OrderMethodEnum = Field(..., description="주문 방식")
    quantity: Decimal = Field(..., gt=0, description="주문 수량")


class OrderCreate(OrderBase):
    order_price: Optional[Decimal] = Field(None, description="주문 가격 (지정가 주문시)")
    expires_at: Optional[datetime] = Field(None, description="주문 만료일시")
    notes: Optional[str] = Field(None, description="주문 메모")


class OrderUpdate(BaseModel):
    order_price: Optional[Decimal] = Field(None, description="주문 가격")
    quantity: Optional[Decimal] = Field(None, gt=0, description="주문 수량")
    expires_at: Optional[datetime] = Field(None, description="주문 만료일시")
    notes: Optional[str] = Field(None, description="주문 메모")


class OrderCancel(BaseModel):
    cancel_reason: Optional[str] = Field(None, description="취소 사유")


class OrderResponse(InitVarModel):
    id: str
    user_id: str
    stock_id: str
    order_type: OrderTypeEnum
    order_method: OrderMethodEnum
    order_status: OrderStatusEnum
    quantity: Decimal
    order_price: Optional[Decimal]
    executed_quantity: Decimal
    executed_amount: Decimal
    average_price: Optional[Decimal]
    commission: Decimal
    tax: Decimal
    total_fee: Decimal
    order_date: datetime
    executed_date: Optional[datetime]
    cancelled_date: Optional[datetime]
    expires_at: Optional[datetime]
    notes: Optional[str]
    is_simulated: bool
    created_at: datetime
    updated_at: datetime


class OrderExecutionResponse(InitVarModel):
    id: str
    order_id: str
    execution_price: Decimal
    execution_quantity: Decimal
    execution_amount: Decimal
    execution_time: datetime
    execution_fee: Decimal
    created_at: datetime


class OrderWithExecutionsResponse(OrderResponse):
    executions: List[OrderExecutionResponse] = Field(default=[], description="체결 내역")


class OrderListResponse(PagedResponse[OrderWithExecutionsResponse]):
    pass


class OrderSearchRequest(BaseModel):
    stock_id: Optional[str] = Field(None, description="주식 종목 ID")
    order_type: Optional[OrderTypeEnum] = Field(None, description="주문 유형")
    order_status: Optional[OrderStatusEnum] = Field(None, description="주문 상태")
    start_date: Optional[datetime] = Field(None, description="검색 시작일")
    end_date: Optional[datetime] = Field(None, description="검색 종료일")


class OrderSummaryResponse(BaseModel):
    total_orders: int = Field(..., description="총 주문 수")
    pending_orders: int = Field(..., description="대기중인 주문 수")
    filled_orders: int = Field(..., description="체결된 주문 수")
    cancelled_orders: int = Field(..., description="취소된 주문 수")
    total_buy_amount: Decimal = Field(..., description="총 매수 금액")
    total_sell_amount: Decimal = Field(..., description="총 매도 금액")
    total_commission: Decimal = Field(..., description="총 수수료")


class QuickOrderRequest(BaseModel):
    """빠른 주문 요청 (시장가 매수/매도)"""
    stock_id: str = Field(..., description="주식 종목 ID")
    order_type: OrderTypeEnum = Field(..., description="주문 유형")
    amount: Optional[Decimal] = Field(None, description="매수 금액 (매수시)")
    quantity: Optional[Decimal] = Field(None, description="매도 수량 (매도시)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "stock_id": "stock-uuid-123",
                "order_type": "BUY",
                "amount": 1000000  # 100만원어치 매수
            }
        }
    }