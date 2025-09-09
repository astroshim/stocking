from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.api.schemas.init_var_model import InitVarModel


class BalanceChangeTypeEnum(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    BUY = "BUY"
    SELL = "SELL"
    INITIAL_DEPOSIT = "INITIAL_DEPOSIT"


class VirtualBalanceResponse(InitVarModel):
    id: str
    user_id: str
    cash_balance: Decimal
    available_cash: Decimal
    invested_amount: Decimal
    last_trade_date: Optional[datetime]
    last_updated_at: datetime
    created_at: datetime
    updated_at: datetime
    # 추가 필드
    total_assets: Optional[Decimal] = Field(None, description="총 자산 (주문가능금액 + 현재주식가치)")
    portfolio_value: Optional[Decimal] = Field(None, description="현재 주식 가치")
    profit_loss_rate: Optional[Decimal] = Field(None, description="손익률 (%)")


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
