from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class StockPriceDetail(BaseModel):
    """종목 가격 상세 정보 (한국주식/미국주식 공통)"""
    # 공통 필수 필드
    code: str = Field(..., description="종목 코드 (예: A456160, US19801212001)")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가") 
    low: float = Field(..., description="저가")
    close: float = Field(..., description="현재가/종가")
    volume: int = Field(..., description="거래량")
    value: int = Field(..., description="거래 대금")
    base: float = Field(..., description="기준가")
    changeType: str = Field(..., description="등락 구분 (UP/DOWN/FLAT)")
    currency: str = Field(..., description="통화 (KRW/USD)")
    high52w: float = Field(..., description="52주 최고가")
    low52w: float = Field(..., description="52주 최저가")
    high1y: float = Field(..., description="1년 최고가")
    low1y: float = Field(..., description="1년 최저가")
    marketCap: int = Field(..., description="시가총액")
    tradingStrength: float = Field(..., description="체결강도")
    preDayVolume: int = Field(..., description="전일 거래량")
    
    # 한국주식 특화 필드 (선택사항)
    exchange: Optional[str] = Field(None, description="거래소 구분 (예: integrated)")
    tradeDateTime: Optional[str] = Field(None, description="거래 시간 (ISO format)")
    upperLimit: Optional[float] = Field(None, description="상한가")
    lowerLimit: Optional[float] = Field(None, description="하한가")
    krxTradingSuspended: Optional[bool] = Field(None, description="KRX 거래정지 여부")
    nxtTradingSuspended: Optional[bool] = Field(None, description="NXT 거래정지 여부")
    nxtSinglePrice: Optional[bool] = Field(None, description="NXT 단일가 여부")
    krxSinglePrice: Optional[bool] = Field(None, description="KRX 단일가 여부")
    
    # 미국주식 특화 필드 (시간외 거래)
    afterMarketOpen: Optional[float] = Field(None, description="시간외 시가")
    afterMarketHigh: Optional[float] = Field(None, description="시간외 고가")
    afterMarketLow: Optional[float] = Field(None, description="시간외 저가")
    afterMarketClose: Optional[float] = Field(None, description="시간외 종가")
    
    # KRW 변환 필드 (미국주식용)
    afterMarketOpenKrw: Optional[int] = Field(None, description="시간외 시가 (원화)")
    afterMarketHighKrw: Optional[int] = Field(None, description="시간외 고가 (원화)")
    afterMarketLowKrw: Optional[int] = Field(None, description="시간외 저가 (원화)")
    afterMarketCloseKrw: Optional[int] = Field(None, description="시간외 종가 (원화)")
    closeKrw: Optional[int] = Field(None, description="종가 (원화)")
    baseKrw: Optional[int] = Field(None, description="기준가 (원화)")
    closeKrwDecimal: Optional[float] = Field(None, description="종가 (원화, 소수점)")
    baseKrwDecimal: Optional[float] = Field(None, description="기준가 (원화, 소수점)")
    openKrw: Optional[int] = Field(None, description="시가 (원화)")
    highKrw: Optional[int] = Field(None, description="고가 (원화)")
    lowKrw: Optional[int] = Field(None, description="저가 (원화)")
    high52wKrw: Optional[int] = Field(None, description="52주 최고가 (원화)")
    low52wKrw: Optional[int] = Field(None, description="52주 최저가 (원화)")
    high1yKrw: Optional[int] = Field(None, description="1년 최고가 (원화)")
    low1yKrw: Optional[int] = Field(None, description="1년 최저가 (원화)")
    valueKrw: Optional[int] = Field(None, description="거래 대금 (원화)")


class StockPriceDetailsResponse(BaseModel):
    """종목 가격 상세 정보 API 응답 (실제 Toss API 구조)"""
    result: List[StockPriceDetail] = Field(..., description="종목 가격 상세 정보 리스트")
    
    class Config:
        json_schema_extra = {
            "example": {
                # 미국주식 예제
                "result": [
                    {
                        "code": "US19801212001",
                        "open": 237.0,
                        "high": 237.0,
                        "low": 235.67,
                        "close": 235.79,
                        "volume": 12961,
                        "value": 3057910,
                        "base": 229.72,
                        "changeType": "UP",
                        "currency": "USD",
                        "high52w": 260.1,
                        "low52w": 169.21,
                        "high1y": 260.1,
                        "low1y": 169.21,
                        "marketCap": 3499217916000,
                        "tradingStrength": 96.35,
                        "preDayVolume": 39418437,
                        "afterMarketOpen": 0.0,
                        "afterMarketHigh": 0.0,
                        "afterMarketLow": 0.0,
                        "afterMarketClose": 0.0,
                        "afterMarketOpenKrw": 0,
                        "afterMarketHighKrw": 0,
                        "afterMarketLowKrw": 0,
                        "afterMarketCloseKrw": 0,
                        "closeKrw": 328266,
                        "baseKrw": 319816,
                        "closeKrwDecimal": 328266.838,
                        "baseKrwDecimal": 319816.184,
                        "openKrw": 329951,
                        "highKrw": 329951,
                        "lowKrw": 328099,
                        "high52wKrw": 362111,
                        "low52wKrw": 235574,
                        "high1yKrw": 362111,
                        "low1yKrw": 235574,
                        "valueKrw": 4257222302
                    }
                ]
            }
        }


# 간편한 현재가 정보만 추출하는 스키마
class CurrentPriceInfo(BaseModel):
    """현재가 정보 (간소화)"""
    code: str = Field(..., description="종목 코드")
    current_price: float = Field(..., description="현재가 (USD/KRW)")
    change_type: str = Field(..., description="등락 구분")
    currency: str = Field(..., description="통화 (USD/KRW)")
    
    @classmethod
    def from_stock_price_detail(cls, detail: StockPriceDetail) -> "CurrentPriceInfo":
        """StockPriceDetail에서 현재가 정보만 추출"""
        return cls(
            code=detail.code,
            current_price=detail.close,
            change_type=detail.changeType,
            currency=detail.currency
        )
