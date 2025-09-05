from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum
from app.db.models.order import OrderType, OrderMethod, OrderStatus, ExitReason
from enum import Enum

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


"""
API 스키마에서 별도의 Enum을 정의하지 않고, 도메인 모델(Enum)을 단일 소스로 사용합니다.
Pydantic은 표준 Enum을 정상적으로 직렬화/검증하므로 OpenAPI에도 문자열 값으로 노출됩니다.
"""


class OrderBase(BaseModel):
    stock_id: str = Field(..., description="주식 종목 ID")
    order_type: OrderType = Field(
        ..., 
        description="주문 유형 (BUY=매수, SELL=매도)"
    )
    order_method: OrderMethod = Field(
        ..., 
        description="주문 방식 (MARKET=시장가, LIMIT=지정가)"
    )
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
    product_code: str
    product_name: str
    market: str
    order_type: OrderType
    order_method: OrderMethod
    order_status: OrderStatus = Field(
        ..., 
        description="주문 상태 (PENDING=대기중, PARTIALLY_FILLED=부분체결, FILLED=체결완료, CANCELLED=취소됨, REJECTED=거부됨, EXPIRED=만료됨)"
    )
    quantity: Decimal
    order_price: Optional[Decimal]
    executed_quantity: Decimal
    executed_amount: Decimal
    average_price: Optional[Decimal]
    # 환율 및 통화 정보
    currency: str
    exchange_rate: Optional[Decimal] = None
    krw_order_price: Optional[Decimal] = None
    krw_executed_amount: Optional[Decimal] = None
    
    # 수수료/세금
    commission: Decimal
    tax: Decimal
    total_fee: Decimal
    # 시간/메모
    order_date: datetime
    executed_date: Optional[datetime]
    cancelled_date: Optional[datetime]
    expires_at: Optional[datetime]
    notes: Optional[str]
    exit_reason: Optional[ExitReason]
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
    order_type: Optional[OrderType] = Field(None, description="주문 유형 (BUY=매수, SELL=매도)")
    order_status: Optional[OrderStatus] = Field(
        None, 
        description="주문 상태 (PENDING=대기중, PARTIALLY_FILLED=부분체결, FILLED=체결완료, CANCELLED=취소됨, REJECTED=거부됨, EXPIRED=만료됨)"
    )
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
    order_type: OrderType = Field(..., description="주문 유형 (BUY=매수, SELL=매도)")
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