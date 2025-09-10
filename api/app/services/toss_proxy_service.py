import random
import logging
from typing import Optional, Dict, Any, List
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
        self._validate_product_code_prefix(product_code)
        return self.proxy_get(f"/api/v2/stock-infos/{product_code}")
    
    def get_stock_price_details(self, product_code: str) -> Dict[str, Any]:
        """종목 거래 현황 조회"""
        self._validate_product_code_prefix(product_code)
        params = {"productCodes": f"{product_code}"}
        return self.proxy_get("/api/v3/stock-prices/details", params=params)
    
    def get_stock_price(self, product_code: str) -> Optional[Dict[str, Any]]:
        """
        종목의 현재가 정보를 조회합니다.
        
        Args:
            product_code: 종목 코드 (예: 'A005930', 'USAAPL')
            
        Returns:
            종목 가격 정보 딕셔너리 또는 None
            {
                'current_price': Decimal,  # 현재가
                'previous_close': Decimal,  # 전일 종가
                'open': Decimal,           # 시가
                'high': Decimal,           # 고가
                'low': Decimal,            # 저가
                'volume': int,             # 거래량
                'change_type': str,        # 변동 타입 (UP/DOWN/FLAT)
                'currency': str            # 통화
            }
        """
        try:
            # 종목 상세 가격 정보 조회
            response = self.get_stock_price_details(product_code)
            
            if not response or 'result' not in response:
                logging.warning(f"No price data found for {product_code}")
                return None
            
            result = response.get('result', [])
            if not result or not isinstance(result, list) or len(result) == 0:
                logging.warning(f"Empty result for {product_code}")
                return None
            
            # 첫 번째 결과 사용 (productCodes는 단일 종목)
            price_data = result[0]
            
            # 현재가 결정: close가 가장 최신 가격
            current_price = price_data.get('close', 0)
            
            # 전일 종가 (base)
            previous_close = price_data.get('base', 0)
            
            return {
                'current_price': Decimal(str(current_price)) if current_price else Decimal('0'),
                'previous_close': Decimal(str(previous_close)) if previous_close else Decimal('0'),
                'open': Decimal(str(price_data.get('open', 0))) if price_data.get('open') else Decimal('0'),
                'high': Decimal(str(price_data.get('high', 0))) if price_data.get('high') else Decimal('0'),
                'low': Decimal(str(price_data.get('low', 0))) if price_data.get('low') else Decimal('0'),
                'volume': price_data.get('volume', 0),
                'change_type': price_data.get('changeType', 'FLAT'),
                'currency': price_data.get('currency', 'KRW'),
                'market_cap': price_data.get('marketCap', 0),
                'high_52w': Decimal(str(price_data.get('high52w', 0))) if price_data.get('high52w') else Decimal('0'),
                'low_52w': Decimal(str(price_data.get('low52w', 0))) if price_data.get('low52w') else Decimal('0')
            }
            
        except Exception as e:
            logging.error(f"Error fetching stock price for {product_code}: {str(e)}")
            return None
    
    def get_stock_prices_batch(self, product_codes: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        여러 종목의 현재가 정보를 한 번에 조회합니다.
        
        Args:
            product_codes: 종목 코드 리스트 (예: ['A005930', 'A000660', 'USAAPL'])
            
        Returns:
            종목 코드를 키로 하는 가격 정보 딕셔너리
            {
                'A005930': {
                    'current_price': Decimal,
                    'previous_close': Decimal,
                    ...
                },
                'A000660': {...},
                ...
            }
        """
        if not product_codes:
            return {}
        
        try:
            # 종목 코드들을 쉼표로 구분하여 한 번에 요청
            params = {"productCodes": ",".join(product_codes)}
            response = self.proxy_get("/api/v3/stock-prices/details", params=params)
            
            if not response or 'result' not in response:
                logging.warning(f"No price data found for batch request")
                return {code: None for code in product_codes}
            
            results = response.get('result', [])
            if not results or not isinstance(results, list):
                return {code: None for code in product_codes}
            
            # 결과를 종목 코드별로 매핑
            price_map = {}
            for price_data in results:
                code = price_data.get('code')
                if not code:
                    continue
                
                # 현재가 결정: close가 가장 최신 가격
                current_price = price_data.get('close', 0)
                previous_close = price_data.get('base', 0)
                
                price_map[code] = {
                    'current_price': Decimal(str(current_price)) if current_price else Decimal('0'),
                    'previous_close': Decimal(str(previous_close)) if previous_close else Decimal('0'),
                    'open': Decimal(str(price_data.get('open', 0))) if price_data.get('open') else Decimal('0'),
                    'high': Decimal(str(price_data.get('high', 0))) if price_data.get('high') else Decimal('0'),
                    'low': Decimal(str(price_data.get('low', 0))) if price_data.get('low') else Decimal('0'),
                    'volume': price_data.get('volume', 0),
                    'change_type': price_data.get('changeType', 'FLAT'),
                    'currency': price_data.get('currency', 'KRW'),
                    'market_cap': price_data.get('marketCap', 0),
                    'high_52w': Decimal(str(price_data.get('high52w', 0))) if price_data.get('high52w') else Decimal('0'),
                    'low_52w': Decimal(str(price_data.get('low52w', 0))) if price_data.get('low52w') else Decimal('0')
                }
            
            # 요청한 종목 중 결과가 없는 것들은 None으로 설정
            for code in product_codes:
                if code not in price_map:
                    price_map[code] = None
            
            return price_map
            
        except Exception as e:
            logging.error(f"Error fetching stock prices batch: {str(e)}")
            return {code: None for code in product_codes}
    
    def get_stock_overview(self, product_code: str) -> Dict[str, Any]:
        """종목 주요정보 조회"""
        self._validate_product_code_prefix(product_code)
        return self.proxy_get(f"/api/v2/stock-infos/{product_code}/overview")

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

    @staticmethod
    def _validate_product_code_prefix(product_code: str) -> None:
        """product_code는 'US' 또는 'A'로 시작해야 함"""
        if not (isinstance(product_code, str) and (product_code.startswith('US') or product_code.startswith('A') or product_code.startswith('NAS'))):
            raise ValidationError("product_code는 'US' 또는 'A', 'NAS' 로 시작해야 합니다")
    