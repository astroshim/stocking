import random
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
import requests
from fastapi import HTTPException

from app.exceptions.custom_exceptions import ValidationError


class TossProxyService:
    """Toss API 프록시 서비스"""
    
    # Toss API Base URLs
    INFO_BASE_URL = "https://wts-info-api.tossinvest.com"
    CERT_BASE_URL = "https://wts-cert-api.tossinvest.com"

    USER_AGENTS = [
        # ===== Desktop (Windows/macOS/Linux) ~25 =====
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/125.0.0.0 Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/126.0.0.0 Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        # Android Tablets 등 더 많은 User-Agent들...
    ]
    
    def __init__(self):
        # 환율 캐시 (1분간 유효)
        self._exchange_rate_cache = {}
        self._cache_timestamp = {}
    
    def proxy_post(self, path: str, body: Optional[Dict] = None, base_url: str = None) -> Dict[str, Any]:
        """Generic POST proxy with configurable base URL"""
        if base_url is None:
            base_url = self.CERT_BASE_URL
        url = f"{base_url}{path}"
        try:
            headers = {
                "User-Agent": random.choice(self.USER_AGENTS),
                "content-type": "application/json",
                "Origin": "https://www.tossinvest.com",
                "Referer": "https://www.tossinvest.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
            }
            resp = requests.post(url, json=body, headers=headers, timeout=10.0)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream proxy error: {str(e)}")

    def proxy_get(self, path: str, params: Optional[dict] = None, base_url: str = None) -> Dict[str, Any]:
        """Generic GET proxy with configurable base URL"""
        if base_url is None:
            base_url = self.INFO_BASE_URL
        url = f"{base_url}{path}"
        try:
            headers = {
                "User-Agent": random.choice(self.USER_AGENTS),
                "Origin": "https://www.tossinvest.com",
                "Referer": "https://www.tossinvest.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
            }
            resp = requests.get(url, params=params, headers=headers, timeout=10.0)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream proxy error: {str(e)}")
    
    def get_stock_info(self, product_code: str) -> Dict[str, Any]:
        """종목 기본정보 조회"""
        return self.proxy_get(f"/api/v2/stock-infos/{product_code}")
    
    def get_stock_price_details(self, product_code: str) -> Dict[str, Any]:
        """종목 거래 현황 조회"""
        params = {"productCodes": f"{product_code}"}
        return self.proxy_get("/api/v3/stock-prices/details", params=params)
    
    def get_exchange_rate(self, from_currency: str, to_currency: str = 'KRW') -> Decimal:
        """
        환율을 조회합니다.
        
        Args:
            from_currency: 기준 통화 (USD, EUR, JPY 등)
            to_currency: 목표 통화 (기본: KRW)
            
        Returns:
            환율 (from_currency 1단위 = ? to_currency)
        """
        # KRW -> KRW인 경우
        if from_currency == to_currency:
            return Decimal('1.0')
            
        cache_key = f"{from_currency}_{to_currency}"
        
        # 캐시 확인 (1분 이내)
        if (cache_key in self._exchange_rate_cache and 
            cache_key in self._cache_timestamp and
            datetime.now() - self._cache_timestamp[cache_key] < timedelta(minutes=1)):
            return self._exchange_rate_cache[cache_key]
            
        # Toss API를 통한 실시간 환율 조회
        rate = self._fetch_exchange_rate_from_toss(from_currency, to_currency)
        
        # 캐시 저장
        self._exchange_rate_cache[cache_key] = rate
        self._cache_timestamp[cache_key] = datetime.now()
        
        logging.info(f"환율 조회 성공 (Toss API): 1 {from_currency} = {rate} {to_currency}")
        return rate
    
    def _fetch_exchange_rate_from_toss(self, from_currency: str, to_currency: str) -> Decimal:
        """Toss API를 통해 실시간 환율을 조회합니다."""
        try:
            # Toss API 환율 조회 파라미터
            params = {
                "buyCurrency": from_currency,   # 매수 통화 (예: USD)
                "sellCurrency": to_currency     # 매도 통화 (예: KRW)
            }
            
            # Toss API 호출
            response = self.proxy_get("/api/v1/product/exchange-rate", params=params)

            logging.info(f"-----------> 환율 response: {response}")
            
            # 응답 데이터에서 환율 추출
            if not response or not isinstance(response, dict):
                raise ValidationError("Invalid response format from Toss API")
            
            # Toss API 응답 구조: {"result": {"code": "EXCHANGE_RATE", "base": 1392.2, "close": 1389.85}}
            # close 값이 1달러의 원화 가격
            if 'result' not in response:
                raise ValidationError(f"'result' field not found in response: {response}")
                
            result = response['result']
            if not isinstance(result, dict) or 'close' not in result:
                raise ValidationError(f"'close' field not found in result: {result}")
            
            close_rate = result['close']
            if close_rate is None or close_rate <= 0:
                raise ValidationError(f"Invalid close rate: {close_rate}")
                
            rate = Decimal(str(close_rate))
            logging.info(f"Toss API 환율 조회: 1 {from_currency} = {rate} {to_currency} (close 가격)")
            return rate
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Toss API 환율 조회 실패: {str(e)}")
    
    # def convert_currency(
    #     self, 
    #     amount: Decimal, 
    #     from_currency: str, 
    #     to_currency: str = 'KRW'
    # ) -> Decimal:
    #     """
    #     통화를 변환합니다.
        
    #     Args:
    #         amount: 변환할 금액
    #         from_currency: 기준 통화
    #         to_currency: 목표 통화
            
    #     Returns:
    #         변환된 금액
    #     """
    #     if from_currency == to_currency:
    #         return amount
            
    #     exchange_rate = self.get_exchange_rate(from_currency, to_currency)
    #     converted_amount = amount * exchange_rate
        
    #     logging.info(f"통화 변환: {amount} {from_currency} = {converted_amount} {to_currency} (환율: {exchange_rate})")
    #     return converted_amount
    
    # def get_supported_currencies(self) -> list:
    #     """지원하는 통화 목록을 반환합니다."""
    #     return ['KRW', 'USD', 'EUR', 'JPY', 'CNY', 'GBP', 'CAD', 'AUD', 'SGD', 'HKD']
    
    # def validate_currency(self, currency: str) -> bool:
    #     """통화 코드가 유효한지 확인합니다."""
    #     return currency.upper() in self.get_supported_currencies()
