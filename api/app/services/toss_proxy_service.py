import random
from typing import Optional, Dict, Any
import requests
from fastapi import HTTPException


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
        pass
    
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
