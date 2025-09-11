from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.api.schemas.common_pagenation import PagedResponse
from app.api.schemas.init_var_model import InitVarModel


class TransactionTypeEnum(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    FEE = "FEE"
    TAX = "TAX"
class OrderBriefResponse(InitVarModel):
    id: str
    product_code: str
    product_name: str
    market: str
    order_type: str
    order_method: str
    currency: str
    exchange_rate: Optional[Decimal]
    order_price: Optional[Decimal]
    krw_order_price: Optional[Decimal]



class TransactionResponse(InitVarModel):
    id: str
    user_id: str
    stock_id: Optional[str]
    order_id: Optional[str]
    transaction_type: TransactionTypeEnum
    quantity: Optional[Decimal]
    price: Optional[Decimal]
    amount: Decimal
    commission: Decimal
    tax: Decimal
    net_amount: Decimal
    cash_balance_before: Decimal
    cash_balance_after: Decimal
    transaction_date: datetime
    settlement_date: Optional[datetime]
    description: Optional[str]
    reference_number: Optional[str]
    is_simulated: bool
    created_at: datetime
    order: Optional[OrderBriefResponse] = None
    
    # 실현손익
    realized_profit_loss: Optional[Decimal] = Field(None, description='실현 손익 (현지통화)')
    krw_realized_profit_loss: Optional[Decimal] = Field(None, description='원화 환산 실현 손익')

    class Config:
        from_attributes = True
        json_schema_extra = {
            "id": "1234567890abcdef1234567890abcdef",
            "user_id": "user123",
            "stock_id": "A00001",
            "order_id": "order123",
            "transaction_type": "BUY",
            "quantity": 10,
            "price": 10000,
            "amount": 100000,
            "commission": 1000,
            "tax": 100,
            "net_amount": 99000,
            "cash_balance_before": 1000000,
            "cash_balance_after": 990000,
            "transaction_date": "2023-10-27T10:00:00",
            "settlement_date": "2023-10-27T10:00:00",
            "description": "Sample transaction",
            "reference_number": "REF123",
            "is_simulated": False,
            "created_at": "2023-10-27T10:00:00",
            "order": {
                "id": "order123",
                "product_code": "A00001",
                "product_name": "Sample Stock",
                "market": "KOSPI",
                "order_type": "LIMIT",
                "order_method": "BUY",
                "currency": "KRW",
                "exchange_rate": 1000,
                "order_price": 10000,
                "krw_order_price": 100000,
            },
            "realized_profit_loss": 1000,
            "krw_realized_profit_loss": 1000000,
        }


class TransactionListResponse(PagedResponse[TransactionResponse]):
    pass


class TransactionSearchRequest(BaseModel):
    transaction_type: Optional[TransactionTypeEnum] = Field(None, description="거래 유형")
    stock_id: Optional[str] = Field(None, description="주식 종목 ID")
    start_date: Optional[datetime] = Field(None, description="검색 시작일")
    end_date: Optional[datetime] = Field(None, description="검색 종료일")
    min_amount: Optional[Decimal] = Field(None, description="최소 거래금액")
    max_amount: Optional[Decimal] = Field(None, description="최대 거래금액")


class DailyStockProfitLossItem(InitVarModel):
    """일별 종목 실현 손익 항목"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    stock_id: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    realized_profit_loss: float = Field(..., description="실현 손익 (원)")
    trade_count: int = Field(..., description="거래 횟수")
    total_sell_quantity: int = Field(..., description="총 매도 수량")
    avg_sell_price: float = Field(..., description="평균 매도가")
    transaction_ids: Optional[List[str]] = Field(None, description="거래 ID 목록")
    # 환율 관련 손익 (해외 주식만 해당)
    price_profit_loss: Optional[float] = Field(None, description="가격 차익 (원)")
    exchange_profit_loss: Optional[float] = Field(None, description="환율 차익 (원)")
    avg_purchase_exchange_rate: Optional[float] = Field(None, description="평균 매수 환율")
    avg_current_exchange_rate: Optional[float] = Field(None, description="평균 매도 시점 환율")


class DailyProfitLossItem(InitVarModel):
    """일별 실현 손익 항목"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    total_realized_profit_loss: float = Field(..., description="일별 총 실현 손익")
    trade_count: int = Field(..., description="일별 총 거래 횟수")
    stock_details: List[DailyStockProfitLossItem] = Field(..., description="종목별 상세")


class PeriodRealizedProfitLossResponse(InitVarModel):
    """기간별 실현 손익 응답 (일/주/월/년/전체)"""
    period_type: str = Field(..., description="기간 타입 (day/week/month/year/all)")
    period_value: Optional[str] = Field(None, description="기간 값 (예: 2024-09-10, 2024-09-2, 2024-09, 2024)")
    total_realized_profit_loss: float = Field(..., description="총 실현 손익")
    total_trades: int = Field(..., description="총 거래 횟수")
    total_profit_loss_rate: Optional[float] = Field(None, description="총 수익률 (%)")
    total_invested_amount: Optional[float] = Field(None, description="총 투자금액 (매도 원가)")
    daily_breakdown: List[DailyProfitLossItem] = Field(..., description="일별 상세 데이터")


class StockRealizedProfitLossItem(InitVarModel):
    """종목별 실현 손익 항목"""
    stock_id: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    total_realized_profit_loss: float = Field(..., description="총 실현 손익")
    total_trades: int = Field(..., description="총 거래 횟수")
    total_sell_quantity: int = Field(..., description="총 매도 수량")
    avg_profit_per_trade: float = Field(..., description="거래당 평균 수익")
    profit_loss_rate: Optional[float] = Field(None, description="수익률 (%)")
    total_invested_amount: Optional[float] = Field(None, description="총 투자금액 (매도 원가)")
    first_trade_date: str = Field(..., description="첫 거래일")
    last_trade_date: str = Field(..., description="마지막 거래일")
    # 환율 관련 손익 (해외 주식만 해당)
    total_price_profit_loss: Optional[float] = Field(None, description="총 가격 차익 (원)")
    total_exchange_profit_loss: Optional[float] = Field(None, description="총 환율 차익 (원)")
    avg_purchase_exchange_rate: Optional[float] = Field(None, description="평균 매수 환율")
    avg_current_exchange_rate: Optional[float] = Field(None, description="평균 매도 시점 환율")


class StockRealizedProfitLossResponse(InitVarModel):
    """종목별 실현 손익 응답"""
    period_type: str = Field(..., description="기간 타입 (day/week/month/year/all)")
    period_value: Optional[str] = Field(None, description="기간 값")
    total_realized_profit_loss: float = Field(..., description="총 실현 손익")
    total_trades: int = Field(..., description="총 거래 횟수")
    total_profit_loss_rate: Optional[float] = Field(None, description="총 수익률 (%)")
    total_invested_amount: Optional[float] = Field(None, description="총 투자금액 (매도 원가)")
    stocks: List[StockRealizedProfitLossItem] = Field(..., description="종목별 데이터")