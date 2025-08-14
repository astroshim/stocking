from typing import Set
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.config.db import SessionLocal
from app.db.models.user import User
from app.services.kis_service import KisWsService, KisWebSocketProvider
from app.config import config
from app.services.kis_service import KisWsService


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

    # stock_id가 있는 경우: 가격 서비스 기반 스트리밍
    if stock_id:
        db: Session | None = None
        try:
            # 사용자 기반 KIS 설정 로드 (없으면 Mock으로 스트리밍)
            db = SessionLocal()
            user_id = websocket.query_params.get("user_id")
            provider = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()

                # 우선순위: 사용자 설정 > 글로벌 설정(config)
                app_key = getattr(user, 'kis_app_key', None) or (config.KIS_APP_KEY or None)
                app_secret = getattr(user, 'kis_app_secret', None) or (config.KIS_APP_SECRET or None)
                if app_key and app_secret:
                    # approval key가 없거나 만료(약 50분) 시 재발급
                    from datetime import datetime, timedelta
                    from app.services.kis_service import KisWsService as _PS
                    ps_tmp = _PS()
                    # approval key는 토큰 스토어(redis/in-memory)에 저장/조회
                    approval = ps_tmp._get_approval(app_key, app_secret)
                    
                    provider = KisWebSocketProvider(app_key, app_secret, approval)

            kis_service = KisWsService(provider)
            # 국내/해외 자동 판별하여 체결(TR) 구독
            async for tick in kis_service.iter_ticks(stock_id, tr_id=None, interval_sec=1.0):
                await websocket.send_text(json.dumps({
                    "stock_id": tick.stock_id,
                    "price": tick.price,
                    "change": tick.change,
                    "change_rate": tick.change_rate,
                    "ts": tick.ts,
                }))
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception:
            # 비정상 종료 방어
            manager.disconnect(websocket)
        finally:
            if db is not None:
                db.close()
    else:
        # stock_id가 없으면 단순 에코 모드
        try:
            while True:
                text = await websocket.receive_text()
                await websocket.send_text(text)
        except WebSocketDisconnect:
            manager.disconnect(websocket)

