from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class StockPriceDetail(BaseModel):
    """종목 가격 상세 정보"""
    code: str = Field(..., description="종목 코드 (예: A456160)")
    exchange: str = Field(..., description="거래소 구분 (예: integrated)")
    tradeDateTime: str = Field(..., description="거래 시간 (ISO format)")
    open: int = Field(..., description="시가")
    high: int = Field(..., description="고가") 
    low: int = Field(..., description="저가")
    close: int = Field(..., description="현재가/종가")
    volume: int = Field(..., description="거래량")
    value: int = Field(..., description="거래 대금")
    base: int = Field(..., description="기준가")
    changeType: str = Field(..., description="등락 구분 (UP/DOWN/FLAT)")
    currency: str = Field(..., description="통화 (예: KRW)")
    high52w: int = Field(..., description="52주 최고가")
    low52w: int = Field(..., description="52주 최저가")
    high1y: int = Field(..., description="1년 최고가")
    low1y: int = Field(..., description="1년 최저가")
    marketCap: int = Field(..., description="시가총액")
    tradingStrength: float = Field(..., description="체결강도")
    upperLimit: int = Field(..., description="상한가")
    lowerLimit: int = Field(..., description="하한가")
    preDayVolume: int = Field(..., description="전일 거래량")
    krxTradingSuspended: bool = Field(..., description="KRX 거래정지 여부")
    nxtTradingSuspended: bool = Field(..., description="NXT 거래정지 여부")
    nxtSinglePrice: bool = Field(..., description="NXT 단일가 여부")
    krxSinglePrice: bool = Field(..., description="KRX 단일가 여부")


class StockPriceDetailsResponse(BaseModel):
    """종목 가격 상세 정보 API 응답 (실제 Toss API 구조)"""
    result: List[StockPriceDetail] = Field(..., description="종목 가격 상세 정보 리스트")
    
    class Config:
        schema_extra = {
            "example": {
                "result": [
                    {
                        "code": "A456160",
                        "exchange": "integrated",
                        "tradeDateTime": "2025-08-27T07:22:11Z",
                        "open": 138300,
                        "high": 165000,
                        "low": 136000,
                        "close": 157800,
                        "volume": 2846092,
                        "value": 438039991300,
                        "base": 138300,
                        "changeType": "UP",
                        "currency": "KRW",
                        "high52w": 165000,
                        "low52w": 82700,
                        "high1y": 165000,
                        "low1y": 82700,
                        "marketCap": 846706513200,
                        "tradingStrength": 95.0,
                        "upperLimit": 179700,
                        "lowerLimit": 96900,
                        "preDayVolume": 1831503,
                        "krxTradingSuspended": False,
                        "nxtTradingSuspended": False,
                        "nxtSinglePrice": False,
                        "krxSinglePrice": False
                    }
                ]
            }
        }


# 간편한 현재가 정보만 추출하는 스키마
class CurrentPriceInfo(BaseModel):
    """현재가 정보 (간소화)"""
    code: str = Field(..., description="종목 코드")
    current_price: int = Field(..., description="현재가")
    change_type: str = Field(..., description="등락 구분")
    
    @classmethod
    def from_stock_price_detail(cls, detail: StockPriceDetail) -> "CurrentPriceInfo":
        """StockPriceDetail에서 현재가 정보만 추출"""
        return cls(
            code=detail.code,
            current_price=detail.close,
            change_type=detail.changeType
        )
