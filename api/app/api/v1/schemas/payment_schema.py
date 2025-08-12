from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from enum import Enum

from app.api.schemas.init_var_model import InitVarModel
from app.db.models.payment_status import PaymentStatus


class PaymentType(str, Enum):
    """결제 유형"""
    CHARGE = "charge"  # 충전
    PAYMENT = "payment"  # 결제


class PaymentBase(BaseModel):
    """결제 기본 모델"""
    amount: Decimal = Field(..., gt=0, description="결제 금액")
    description: Optional[str] = Field(None, description="결제 설명")


class ChargeRequest(PaymentBase):
    """충전 요청 모델"""
    pass


class PaymentRequest(PaymentBase):
    """결제 요청 모델"""
    pass


class VirtualBalanceDepositRequest(BaseModel):
    """가상 잔고 입금 요청 모델"""
    amount: Decimal = Field(..., gt=0, description="입금할 금액")
    description: Optional[str] = Field(None, description="입금 설명")


class VirtualBalanceWithdrawRequest(BaseModel):
    """가상 잔고 출금 요청 모델"""
    amount: Decimal = Field(..., gt=0, description="출금할 금액")
    description: Optional[str] = Field(None, description="출금 설명")


class VirtualBalanceInitRequest(BaseModel):
    """가상 잔고 초기화 요청 모델"""
    initial_amount: Decimal = Field(default=Decimal('1000000'), gt=0, description="초기 잔고 금액")


class VirtualBalanceResponse(InitVarModel):
    """가상 잔고 응답 모델"""
    id: str
    user_id: str
    cash_balance: float
    available_cash: float
    invested_amount: float
    total_buy_amount: float
    total_sell_amount: float
    total_commission: float
    total_tax: float
    created_at: int
    updated_at: int


class PaymentResponse(InitVarModel):
    """결제 응답 모델"""
    id: str
    user_id: str
    amount: float
    payment_type: str
    status: str
    description: str = ""
    created_at: int

    _timestamp_fields = {'created_at'}
    _default_values = {
        'description': '',
    }


class PaymentCallbackRequest(BaseModel):
    """결제 콜백 요청 모델"""
    payment_id: str = Field(..., description="결제 ID")
    user_id: Optional[str] = Field(None, description="사용자 ID")

    amount: Decimal = Field(..., description="결제 금액")
    status: PaymentStatus = Field(..., description="결제 상태")
    transaction_id: Optional[str] = Field(None, description="결제사 거래 ID")
    payment_method: Optional[str] = Field(None, description="결제 방법")
    payment_time: Optional[str] = Field(None, description="결제 시간")
    extra_data: Optional[dict] = Field(None, description="추가 데이터")
