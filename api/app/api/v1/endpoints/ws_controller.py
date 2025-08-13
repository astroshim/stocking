from typing import Set
import asyncio
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # stock_id를 쿼리 파라미터로 수신
    stock_id = websocket.query_params.get("stock_id")
    await manager.connect(websocket)

    # stock_id가 있는 경우: 해당 종목의 랜덤 가격 스트리밍
    if stock_id:
        try:
            # 초기 가격 설정 (임의 기준값)
            price = random.uniform(10000, 20000)
            while True:
                # 소폭 랜덤 변동 (±0.5%)
                delta_rate = random.uniform(-0.005, 0.005)
                new_price = max(0.0, price * (1.0 + delta_rate))
                payload = {
                    "stock_id": stock_id,
                    "price": round(new_price, 2),
                    "change": round(new_price - price, 2),
                    "change_rate": round(((new_price - price) / price * 100.0) if price > 0 else 0.0, 4),
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
                price = new_price
                await websocket.send_text(json.dumps(payload))
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception:
            # 비정상 종료 방어
            manager.disconnect(websocket)
    else:
        # stock_id가 없으면 단순 에코 모드
        try:
            while True:
                text = await websocket.receive_text()
                await websocket.send_text(text)
        except WebSocketDisconnect:
            manager.disconnect(websocket)

