from pydantic import BaseModel, Field
from typing import Optional, List
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
    order: Optional[OrderBriefResponse]


class TransactionListResponse(PagedResponse[TransactionResponse]):
    pass


class TransactionSearchRequest(BaseModel):
    transaction_type: Optional[TransactionTypeEnum] = Field(None, description="거래 유형")
    stock_id: Optional[str] = Field(None, description="주식 종목 ID")
    start_date: Optional[datetime] = Field(None, description="검색 시작일")
    end_date: Optional[datetime] = Field(None, description="검색 종료일")
    min_amount: Optional[Decimal] = Field(None, description="최소 거래금액")
    max_amount: Optional[Decimal] = Field(None, description="최대 거래금액")


class TradingStatisticsResponse(InitVarModel):
    id: str
    user_id: str
    period_type: str
    period_start: datetime
    period_end: datetime
    total_trades: Decimal
    buy_trades: Decimal
    sell_trades: Decimal
    total_buy_amount: Decimal
    total_sell_amount: Decimal
    total_commission: Decimal
    total_tax: Decimal
    realized_profit_loss: Decimal
    win_trades: Decimal
    loss_trades: Decimal
    win_rate: Decimal
    portfolio_value_start: Decimal
    portfolio_value_end: Decimal
    portfolio_return: Decimal
    created_at: datetime
    updated_at: datetime


class TradingPerformanceResponse(BaseModel):
    """거래 성과 분석"""
    period: str = Field(..., description="분석 기간")
    total_return: Decimal = Field(..., description="총 수익률")
    annualized_return: Decimal = Field(..., description="연환산 수익률")
    volatility: Decimal = Field(..., description="변동성")
    sharpe_ratio: Decimal = Field(..., description="샤프 비율")
    max_drawdown: Decimal = Field(..., description="최대 낙폭")
    win_rate: Decimal = Field(..., description="승률")
    profit_factor: Decimal = Field(..., description="수익 팩터")
    average_win: Decimal = Field(..., description="평균 수익")
    average_loss: Decimal = Field(..., description="평균 손실")


class MonthlyPerformanceResponse(BaseModel):
    """월별 성과"""
    year: int
    month: int
    return_rate: Decimal
    trades_count: int
    profit_loss: Decimal


class TradingDashboardResponse(BaseModel):
    """거래 대시보드 데이터"""
    account_summary: dict = Field(..., description="계좌 요약")
    recent_transactions: List[TransactionResponse] = Field(..., description="최근 거래내역")
    portfolio_summary: dict = Field(..., description="포트폴리오 요약")
    performance_metrics: TradingPerformanceResponse = Field(..., description="성과 지표")
    monthly_performance: List[MonthlyPerformanceResponse] = Field(..., description="월별 성과")
    top_gainers: List[dict] = Field(..., description="상위 수익 종목")
    top_losers: List[dict] = Field(..., description="상위 손실 종목")


class MarketDataResponse(BaseModel):
    """시장 데이터"""
    market_indices: List[dict] = Field(..., description="시장 지수")
    market_news: List[dict] = Field(..., description="시장 뉴스")
    trending_stocks: List[dict] = Field(..., description="인기 종목")
    sector_performance: List[dict] = Field(..., description="섹터별 성과")


class OrderBookResponse(BaseModel):
    """호가창 정보"""
    stock_id: str
    timestamp: datetime
    bid_orders: List[dict] = Field(..., description="매수 호가")
    ask_orders: List[dict] = Field(..., description="매도 호가")
    
    
class TradingSignalResponse(BaseModel):
    """매매 신호"""
    stock_id: str
    signal_type: str  # BUY, SELL, HOLD
    confidence: Decimal  # 0-100
    price_target: Optional[Decimal]
    stop_loss: Optional[Decimal]
    reasoning: str
    generated_at: datetime


class RiskAssessmentResponse(BaseModel):
    """리스크 평가"""
    portfolio_risk_score: Decimal = Field(..., description="포트폴리오 리스크 점수 (1-10)")
    concentration_risk: Decimal = Field(..., description="집중도 리스크")
    sector_exposure: dict = Field(..., description="섹터별 노출도")
    volatility_risk: Decimal = Field(..., description="변동성 리스크")
    liquidity_risk: Decimal = Field(..., description="유동성 리스크")
    recommendations: List[str] = Field(..., description="리스크 개선 권장사항")


class BacktestRequest(BaseModel):
    """백테스팅 요청"""
    strategy_name: str = Field(..., description="전략명")
    start_date: datetime = Field(..., description="시작일")
    end_date: datetime = Field(..., description="종료일")
    initial_capital: Decimal = Field(..., description="초기 자본")
    stocks: List[str] = Field(..., description="대상 종목 리스트")
    parameters: dict = Field(..., description="전략 파라미터")


class BacktestResponse(BaseModel):
    """백테스팅 결과"""
    strategy_name: str
    period: str
    initial_capital: Decimal
    final_capital: Decimal
    total_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    win_rate: Decimal
    total_trades: int
    daily_returns: List[dict]
    trade_history: List[dict]
    equity_curve: List[dict]