from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
import time
import json
import requests


@dataclass
class PriceTick:
    stock_id: str
    price: float
    change: float
    change_rate: float
    ts: int  # epoch seconds (UTC)


class BasePriceProvider:
    async def subscribe(self, tr_id: str, tr_key: str, interval_sec: float = 1.0) -> AsyncIterator[float]:
        raise NotImplementedError


class KisWebSocketProvider(BasePriceProvider):
    """
    한국투자증권 오픈트레이딩 API WebSocket 기반 가격 구독 Provider (간략 구현)
    참고: https://github.com/koreainvestment/open-trading-api/blob/49bbdc6b8dc61ed1e753e64f284f560560ae211c/legacy/websocket/python/ws_domestic_overseas_all.py#L4

    실제 사용을 위해서는 발급받은 앱키/시크릿/접속 토큰 및 종목/채널 구독 메시지 포맷에 맞춰야 합니다.
    이 클래스는 환경변수가 없으면 예외를 던지므로, 기본적으로 MockProvider가 사용됩니다.
    """

    def __init__(self, app_key: str, app_secret: str, approval_key: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = approval_key  # websocket approval key
        # 참고 소스 기준 기본값 변경 (@ws://ops.koreainvestment.com:21000)
        # 운영 환경에서는 보안 연결 wss 사용 엔드포인트로 변경될 수 있음.
        self.ws_endpoint = os.getenv("KIS_WS_ENDPOINT", "ws://ops.koreainvestment.com:21000")

    async def subscribe(self, tr_id: str, tr_key: str, interval_sec: float = 1.0) -> AsyncIterator[float]:
        # 의존 라이브러리: websockets (프로젝트 내 의존성 존재)
        import json
        import websockets

        # 구독 메시지 (참고 코드 형식)
        subscribe_msg = {
            "header": {
                "approval_key": self.access_token,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": tr_key
                }
            }
        }

        async for ws in websockets.connect(self.ws_endpoint, ping_interval=None):  # type: ignore
            try:
                await ws.send(json.dumps(subscribe_msg))
                async for msg in ws:
                    try:
                        print(f"-------> kis websocket msg: {msg}")
                        data = json.loads(msg)

                        # 제어 메시지 처리 (PINGPONG/에러 등)
                        if data.get("header", {}).get("tr_id") == "PINGPONG":
                            await ws.pong(msg)
                            continue
                        # 정상 응답이면 무시하고 실데이터 수신 대기
                        continue
                    except Exception:
                        # 실데이터: 문자열 파싱
                        if not isinstance(msg, str) or len(msg) == 0:
                            continue

                        # print(f"-------> msg: {msg}")
                        # 첫 글자 '0' → 실시간 데이터, '1' → 체결통보 데이터, 그 외 JSON
                        if msg[0] == '0':
                            parts = msg.split('|')
                            if len(parts) < 4:
                                continue
                            cur_tr_id = parts[1]
                            payload = parts[3]
                            fields = payload.split('^') if payload else []
                            price = None
                            if cur_tr_id == 'H0STCNT0':  # 국내 체결: 현재가 index 2
                                if len(fields) > 2:
                                    price = fields[2]
                            elif cur_tr_id == 'HDFSCNT0':  # 해외 체결: 현재가 index 11
                                if len(fields) > 11:
                                    price = fields[11]
                            elif cur_tr_id == 'H0STASP0':  # 국내 호가: 최우선 매수/매도 → 중간가 산출
                                # 매도호가01 index 3, 매수호가01 index 13 (참고 소스 기준)
                                try:
                                    ask = float(fields[3]) if len(fields) > 3 and fields[3] else None
                                    bid = float(fields[13]) if len(fields) > 13 and fields[13] else None
                                    if ask is not None and bid is not None:
                                        price = (ask + bid) / 2.0
                                except Exception:
                                    price = None
                            elif cur_tr_id in ('HDFSASP0', 'HDFSASP1'):  # 해외 호가: 최우선 매수/매도 → 중간가 산출
                                # 매수호가 index 11, 매도호가 index 12 (참고 소스 기준)
                                try:
                                    bid = float(fields[11]) if len(fields) > 11 and fields[11] else None
                                    ask = float(fields[12]) if len(fields) > 12 and fields[12] else None
                                    if ask is not None and bid is not None:
                                        price = (ask + bid) / 2.0
                                except Exception:
                                    price = None
                            # 기타 TR은 스킵
                            if price is None:
                                continue
                            try:
                                yield round(float(price), 2)
                            except Exception:
                                continue
                        else:
                            # 체결통보/기타 메시지는 현재 스트리밍 대상 아님
                            continue
            except Exception:
                # 재접속을 위해 잠시 대기
                await asyncio.sleep(1.0)
                continue


from app.services.kis_token_store import TokenStore, InMemoryTokenStore, RedisTokenStore


class KisWsService:
    def __init__(self, provider: Optional[BasePriceProvider] = None, token_store: Optional[TokenStore] = None):
        self.provider = provider 
        # 우선순위: Redis > InMemory
        self.token_store = token_store or (RedisTokenStore() if os.getenv("REDIS_URL") else InMemoryTokenStore())

    # 웹소켓 접속키 발급 (사용자별 캐시)
    def _get_approval(self, app_key: str, app_secret: str) -> str:
        cache_key = f"kis:approval:{app_key}"
        cached = self.token_store.get(cache_key)
        if cached:
            return cached

        url = 'https://openapi.koreainvestment.com:9443'
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret
        }
        path = "oauth2/Approval"
        api_url = f"{url}/{path}"
        time.sleep(0.05)

        print(f"-------> api_url: {api_url}")
        print(f"-------> headers: {headers}")
        print(f"-------> body: {body}")

        res = requests.post(api_url, headers=headers, data=json.dumps(body))
        print(f"-------> res: {res.json()}")

        res.raise_for_status()
        approval_key = res.json().get("approval_key")
        print(f"-------> approval_key: {approval_key}")

        if not approval_key:
            raise RuntimeError("KIS approval_key 발급 실패")
        # 50분 TTL 저장
        self.token_store.set(cache_key, approval_key, ttl_seconds=50*60)
        return approval_key

    async def iter_ticks(self, stock_id: str, tr_id: Optional[str] = None, interval_sec: float = 1.0) -> AsyncIterator[PriceTick]:
        prev_price: Optional[float] = None
        # tr_id 기본값: 종목 형식으로 추정 (6자리 숫자 → 국내, 그 외 → 해외)
        if not tr_id:
            if stock_id.isdigit() and len(stock_id) == 6:
                tr_id = 'H0STASP0'
            else:
                tr_id = 'HDFSASP0'

        print(f"-------> tr_id: {tr_id}")
        print(f"-------> stock_id: {stock_id}")

        async for price in self.provider.subscribe(tr_id, stock_id, interval_sec=interval_sec):
            if prev_price is None:
                change = 0.0
                change_rate = 0.0
            else:
                change = round(price - prev_price, 2)
                change_rate = round(((price - prev_price) / prev_price * 100.0) if prev_price > 0 else 0.0, 4)

            prev_price = price
            yield PriceTick(
                stock_id=stock_id,
                price=price,
                change=change,
                change_rate=change_rate,
                ts=int(datetime.now(timezone.utc).timestamp()),
            )


