from typing import Set, Dict, Optional
import asyncio
import json
import time
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.config.db import SessionLocal
from app.db.models.user import User
from app.services.redis_service import RedisService
from app.config.di import get_redis_service
from websockets.exceptions import ConnectionClosed


router = APIRouter()
logger = logging.getLogger(__name__)


class TossConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_subscriptions: Dict[str, Set[str]] = {}  # {client_id: {stock_codes}}
        self.stock_subscribers: Dict[str, Set[str]] = {}  # {stock_code: {client_ids}}
        self.client_redis_tasks: Dict[str, asyncio.Task] = {}  # {client_id: redis_listen_task}
        self.client_disconnect_events: Dict[str, asyncio.Event] = {}  # {client_id: disconnect_event}

    async def connect(self, websocket: WebSocket, client_id: str):
        """WebSocket 연결 처리"""
        logger.info(f"🔌 Toss WebSocket 연결 시도 - Client: {client_id}")
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_subscriptions[client_id] = set()
        logger.info(f"✅ Toss WebSocket 연결 완료 - Client: {client_id}, 총 연결: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket, client_id: str):
        """WebSocket 연결 해제 처리"""
        logger.info(f"🔴 Toss WebSocket disconnect 호출됨 - Client: {client_id}")
        
        # 1. active_connections에서 제거
        if websocket in self.active_connections:
            self.active_connections.discard(websocket)
            logger.info(f"✅ active_connections에서 제거됨 - Client: {client_id}, 남은 연결: {len(self.active_connections)}")
        
        # 2. 구독 정리
        await self._cleanup_client_subscriptions(client_id)
        
        # 3. Redis 리스너 태스크 정리
        if client_id in self.client_redis_tasks:
            task = self.client_redis_tasks[client_id]
            if not task.done():
                task.cancel()
            del self.client_redis_tasks[client_id]
            logger.info(f"✅ Redis 리스너 태스크 정리 완료 - Client: {client_id}")
        
        # 4. Disconnect 이벤트 정리
        if client_id in self.client_disconnect_events:
            del self.client_disconnect_events[client_id]
        
        logger.info(f"✅ Toss WebSocket 연결 해제 완료 - Client: {client_id}")

    async def subscribe_stock(self, client_id: str, stock_code: str, websocket: WebSocket, redis_service: RedisService) -> bool:
        """주식 실시간 데이터 구독"""
        try:
            # 클라이언트 구독 목록에 추가
            if client_id not in self.client_subscriptions:
                self.client_subscriptions[client_id] = set()
            self.client_subscriptions[client_id].add(stock_code)
            
            # 주식별 구독자 목록에 추가
            if stock_code not in self.stock_subscribers:
                self.stock_subscribers[stock_code] = set()
            self.stock_subscribers[stock_code].add(client_id)
            
            # Redis 리스너 태스크 시작 (클라이언트당 하나)
            if client_id not in self.client_redis_tasks:
                # 연결 해제 이벤트 생성
                disconnect_event = asyncio.Event()
                
                task = asyncio.create_task(
                    self._redis_listener(client_id, websocket, redis_service, disconnect_event)
                )
                self.client_redis_tasks[client_id] = task
                self.client_disconnect_events[client_id] = disconnect_event  # 이벤트 저장
                logger.info(f"🎧 Redis 리스너 태스크 시작 - Client: {client_id}")
            
            # TossWsRelayer에 동적 구독 요청
            await self._request_toss_subscription(stock_code, redis_service)
            
            # 기존 데이터가 있다면 즉시 전송
            await self._send_existing_data(stock_code, websocket, redis_service)
            
            logger.info(f"✅ Toss 주식 구독 성공 - Client: {client_id}, Stock: {stock_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Toss 주식 구독 실패 - Client: {client_id}, Stock: {stock_code}, Error: {e}")
            return False

    async def unsubscribe_stock(self, client_id: str, stock_code: str, redis_service: RedisService) -> bool:
        """주식 실시간 데이터 구독 해제"""
        try:
            # 클라이언트 구독 목록에서 제거
            if client_id in self.client_subscriptions:
                self.client_subscriptions[client_id].discard(stock_code)
            
            # 주식별 구독자 목록에서 제거
            if stock_code in self.stock_subscribers:
                self.stock_subscribers[stock_code].discard(client_id)
                
                # 해당 주식을 구독하는 클라이언트가 없으면 TossWsRelayer에서도 구독 해제
                if not self.stock_subscribers[stock_code]:
                    await self._request_toss_unsubscription(stock_code, redis_service)
                    del self.stock_subscribers[stock_code]
            
            logger.info(f"✅ Toss 주식 구독 해제 성공 - Client: {client_id}, Stock: {stock_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Toss 주식 구독 해제 실패 - Client: {client_id}, Stock: {stock_code}, Error: {e}")
            return False

    async def _cleanup_client_subscriptions(self, client_id: str):
        """클라이언트의 모든 구독 정리"""
        if client_id in self.client_subscriptions:
            stock_codes = self.client_subscriptions[client_id].copy()
            for stock_code in stock_codes:
                if stock_code in self.stock_subscribers:
                    self.stock_subscribers[stock_code].discard(client_id)
                    if not self.stock_subscribers[stock_code]:
                        del self.stock_subscribers[stock_code]
            
            del self.client_subscriptions[client_id]
            logger.info(f"✅ 클라이언트 구독 정리 완료 - Client: {client_id}")

    async def _request_toss_subscription(self, stock_code: str, redis_service: RedisService):
        """TossWsRelayer에 구독 요청"""
        try:
            from app.services.toss_websocket_command_service import TossWebSocketCommandService
            
            command_service = TossWebSocketCommandService(redis_service.redis_client)
            
            # 주식 코드 형태에 따른 토픽 생성
            if stock_code.startswith('US'):
                # 미국 주식
                topic = f"/topic/v1/us/stock/trade/{stock_code}"
            else:
                # 한국 주식 (기본)
                topic = f"/topic/v1/kr/stock/trade/{stock_code}"
            
            logger.info(f"🎯 구독 요청 토픽 - Stock: {stock_code}, Topic: {topic}")
            
            result = await command_service.send_subscribe_command(topic)
            if result.get('success'):
                logger.info(f"✅ TossWsRelayer 구독 요청 성공 - Stock: {stock_code}")
            else:
                logger.warning(f"⚠️ TossWsRelayer 구독 요청 실패 - Stock: {stock_code}, Result: {result}")
                
        except Exception as e:
            logger.error(f"❌ TossWsRelayer 구독 요청 오류 - Stock: {stock_code}, Error: {e}")

    async def _request_toss_unsubscription(self, stock_code: str, redis_service: RedisService):
        """TossWsRelayer에 구독 해제 요청"""
        try:
            from app.services.toss_websocket_command_service import TossWebSocketCommandService
            
            command_service = TossWebSocketCommandService(redis_service.redis_client)
            
            # 주식 코드 형태에 따른 토픽 생성
            if stock_code.startswith('US'):
                # 미국 주식
                topic = f"/topic/v1/us/stock/trade/{stock_code}"
            else:
                # 한국 주식 (기본)
                topic = f"/topic/v1/kr/stock/trade/{stock_code}"
            
            result = await command_service.send_unsubscribe_command(topic)
            if result.get('success'):
                logger.info(f"✅ TossWsRelayer 구독 해제 요청 성공 - Stock: {stock_code}")
            else:
                logger.warning(f"⚠️ TossWsRelayer 구독 해제 요청 실패 - Stock: {stock_code}, Result: {result}")
                
        except Exception as e:
            logger.error(f"❌ TossWsRelayer 구독 해제 요청 오류 - Stock: {stock_code}, Error: {e}")

    async def _send_existing_data(self, stock_code: str, websocket: WebSocket, redis_service: RedisService):
        """기존 Redis 데이터를 즉시 전송"""
        try:
            existing_data = await redis_service.get_realtime_stock_data(stock_code)
            if existing_data:
                message = {
                    "type": "existing_data",
                    "stock_code": stock_code,
                    "data": existing_data,
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(message))
                logger.info(f"📤 기존 데이터 전송 - Stock: {stock_code}")
                
        except Exception as e:
            logger.error(f"❌ 기존 데이터 전송 실패 - Stock: {stock_code}, Error: {e}")

    async def _redis_listener(self, client_id: str, websocket: WebSocket, redis_service: RedisService, disconnect_event: asyncio.Event):
        """Redis Pub/Sub 리스너 (클라이언트별)"""
        pubsub = None
        
        try:
            logger.info(f"🎧 Redis 리스너 시작 - Client: {client_id}")
            
            # Redis Pub/Sub 설정
            pubsub = redis_service.redis_client.pubsub()
            
            # 한 번만 구독 설정
            current_stocks = self.client_subscriptions.get(client_id, set())
            for stock_code in current_stocks:
                await pubsub.subscribe(f"stock_updates:{stock_code}")
            
            if current_stocks:
                logger.info(f"🔔 Redis 채널 구독 완료 - Client: {client_id}, Stocks: {list(current_stocks)}")
                
                # 메시지 수신 대기 (단일 루프)
                async for message in pubsub.listen():
                    # 연결 상태 체크 (가장 먼저)
                    if websocket not in self.active_connections:
                        logger.info(f"🛑 WebSocket 연결 종료로 Redis 리스너 중단 - Client: {client_id}")
                        disconnect_event.set()  # 메인 루프에 즉시 알림
                        return
                            
                    if message['type'] == 'message':
                        try:
                            # 채널에서 주식 코드 추출
                            channel = message['channel']
                            if channel.startswith('stock_updates:'):
                                stock_code = channel.replace('stock_updates:', '')
                                
                                # 현재 클라이언트가 해당 주식을 구독 중인지 확인
                                if stock_code in self.client_subscriptions.get(client_id, set()):
                                    # WebSocket 연결 상태 재확인
                                    if websocket not in self.active_connections:
                                        logger.info(f"🛑 WebSocket 연결 해제됨, 메시지 전송 중단 - Client: {client_id}")
                                        disconnect_event.set()  # 메인 루프에 즉시 알림
                                        return
                                    
                                    data = json.loads(message['data'])
                                    
                                    # WebSocket으로 실시간 데이터 전송
                                    realtime_message = {
                                        "type": "realtime_update",
                                        "stock_code": stock_code,
                                        "data": data,
                                        "timestamp": time.time()
                                    }
                                    
                                    try:
                                        await websocket.send_text(json.dumps(realtime_message))
                                    except Exception as send_error:
                                        logger.warning(f"⚠️ WebSocket 전송 실패 (연결 해제됨) - Client: {client_id}, Stock: {stock_code}")
                                        # WebSocket이 닫혔으므로 즉시 리스너 종료 및 메인 루프 알림
                                        disconnect_event.set()
                                        return
                                    
                        except Exception as e:
                            logger.error(f"❌ 메시지 처리 오류 - Client: {client_id}, Error: {e}")
                            # 연결 관련 오류인 경우 즉시 리스너 종료 및 메인 루프 알림
                            if "websocket" in str(e).lower() or "connection" in str(e).lower():
                                logger.info(f"🛑 연결 오류로 인한 Redis 리스너 종료 - Client: {client_id}")
                                disconnect_event.set()
                                return
            else:
                logger.info(f"📭 구독할 주식이 없음 - Client: {client_id}")
                
        except asyncio.CancelledError:
            logger.info(f"🛑 Redis 리스너 취소됨 - Client: {client_id}")
            disconnect_event.set()  # 취소 시에도 메인 루프 알림
        except Exception as e:
            logger.error(f"❌ Redis 리스너 오류 - Client: {client_id}, Error: {e}")
            disconnect_event.set()  # 오류 시에도 메인 루프 알림
        finally:
            if pubsub:
                await pubsub.close()
            logger.info(f"✅ Redis 리스너 종료 - Client: {client_id}")


# 전역 연결 매니저
toss_manager = TossConnectionManager()


@router.websocket("/toss-ws")
async def toss_websocket_endpoint(
    websocket: WebSocket,
    redis_service: RedisService = Depends(get_redis_service)
):
    """Toss 실시간 데이터 WebSocket 엔드포인트"""
    
    # 파라미터 수신 (stock_code 또는 stock_id 지원)
    stock_code = websocket.query_params.get("stock_code") or websocket.query_params.get("stock_id")
    user_id = websocket.query_params.get("user_id")
    client_id = str(id(websocket))
    
    logger.info(f"🌟 새로운 Toss WebSocket 연결 요청 - Client: {client_id}, stock_code: {stock_code}, user_id: {user_id}")
    
    await toss_manager.connect(websocket, client_id)

    # stock_code가 있는 경우: Toss 실시간 데이터 구독
    if stock_code:
        db: Session = None
        
        try:
            # 사용자 인증 (선택적)
            db = SessionLocal()
            
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    logger.warning(f"⚠️ 사용자를 찾을 수 없음 - user_id: {user_id}")
                    # 사용자가 없어도 진행 (공개 데이터이므로)
            
            # Toss 실시간 데이터 구독
            success = await toss_manager.subscribe_stock(client_id, stock_code, websocket, redis_service)
            
            if success:
                logger.info(f"✅ Toss 실시간 구독 성공 - Client: {client_id}, Stock: {stock_code}")
                
                # 연결 성공 메시지 전송
                success_msg = {
                    "type": "connection_success",
                    "stock_code": stock_code,
                    "message": f"Toss 실시간 데이터 구독이 시작되었습니다.",
                    "client_id": client_id
                }
                await websocket.send_text(json.dumps(success_msg))
                
                # 무한 대기 (데이터는 Redis 리스너를 통해 전송됨)
                try:
                    ping_count = 0
                    while websocket in toss_manager.active_connections:
                        # Redis 리스너 종료 이벤트와 5초 타임아웃 중 먼저 오는 것 대기
                        disconnect_event = toss_manager.client_disconnect_events.get(client_id)
                        if disconnect_event:
                            try:
                                await asyncio.wait_for(disconnect_event.wait(), timeout=5.0)
                                # Redis 리스너가 연결 해제를 감지했음 - 즉시 루프 종료
                                logger.info(f"🚀 Redis 리스너 종료 신호 수신, 즉시 루프 종료 - Client: {client_id}")
                                break
                            except asyncio.TimeoutError:
                                # 5초 타임아웃 - 정상 상황, 계속 진행
                                pass
                        else:
                            # disconnect_event가 없으면 일반적인 5초 대기
                            await asyncio.sleep(5)
                        
                        # WebSocket 연결 상태 확인
                        if websocket not in toss_manager.active_connections:
                            logger.info(f"🛑 WebSocket active_connections에서 제거됨, 루프 종료 - Client: {client_id}")
                            break
                        
                        # 30초마다 ping 전송 (6회 대기 후)
                        ping_count += 1
                        if ping_count % 6 == 0:  # 5초 * 6 = 30초
                            try:
                                # 연결 확인 ping 전송
                                ping_msg = {
                                    "type": "ping",
                                    "timestamp": time.time(),
                                    "count": ping_count // 6,
                                    "subscribed_stocks": list(toss_manager.client_subscriptions.get(client_id, set()))
                                }
                                await websocket.send_text(json.dumps(ping_msg))
                                logger.debug(f"📡 연결 확인 ping 전송 #{ping_count // 6} - Client: {client_id}")
                                
                            except Exception as ping_e:
                                logger.error(f"❌ 연결 확인 ping 전송 실패 - Client: {client_id}, Error: {ping_e}")
                                logger.info(f"🔴 연결이 끊어진 것으로 판단, 루프 종료 - Client: {client_id}")
                                # 즉시 active_connections에서 제거하여 Redis 리스너도 종료시킴
                                if websocket in toss_manager.active_connections:
                                    toss_manager.active_connections.discard(websocket)
                                    logger.info(f"⚡ ping 실패로 active_connections에서 즉시 제거 - Client: {client_id}")
                                break
                                
                except Exception as e:
                    logger.error(f"❌ 연결 유지 중 오류 - Client: {client_id}, Error: {e}")
                    # 오류 발생 시에도 active_connections에서 제거
                    if websocket in toss_manager.active_connections:
                        toss_manager.active_connections.discard(websocket)
                        logger.info(f"⚡ 오류로 인한 active_connections에서 즉시 제거 - Client: {client_id}")
            else:
                # 구독 실패 메시지
                error_msg = {
                    "type": "error",
                    "message": "Toss 실시간 데이터 구독에 실패했습니다.",
                    "code": "SUBSCRIPTION_FAILED"
                }
                await websocket.send_text(json.dumps(error_msg))
                
        except WebSocketDisconnect as e:
            logger.info(f"🔴 Toss WebSocket 연결 해제 감지 - Client: {client_id}, Code: {e.code}")
            # 즉시 active_connections에서 제거하여 Redis 리스너 종료 트리거
            if websocket in toss_manager.active_connections:
                toss_manager.active_connections.discard(websocket)
                logger.info(f"⚡ WebSocketDisconnect로 active_connections에서 즉시 제거 - Client: {client_id}")
        except ConnectionClosed as e:
            logger.info(f"🔴 Toss WebSocket 연결 닫힘 감지 - Client: {client_id}, Code: {e.code}")
            # 즉시 active_connections에서 제거하여 Redis 리스너 종료 트리거
            if websocket in toss_manager.active_connections:
                toss_manager.active_connections.discard(websocket)
                logger.info(f"⚡ ConnectionClosed로 active_connections에서 즉시 제거 - Client: {client_id}")
        except Exception as e:
            logger.error(f"❌ Toss WebSocket 에러 발생 - Client: {client_id}, Error: {e}")
            # 오류 발생 시에도 즉시 제거
            if websocket in toss_manager.active_connections:
                toss_manager.active_connections.discard(websocket)
                logger.info(f"⚡ 예외 발생으로 active_connections에서 즉시 제거 - Client: {client_id}")
            try:
                error_msg = {
                    "type": "error",
                    "message": f"서버 오류가 발생했습니다: {str(e)}",
                    "code": "SERVER_ERROR"
                }
                await websocket.send_text(json.dumps(error_msg))
            except Exception as send_e:
                logger.error(f"⚠️ 에러 메시지 전송 실패 - Client: {client_id}, Error: {send_e}")
        finally:
            logger.info(f"🔄 Toss WebSocket 정리 시작 - Client: {client_id}")
            
            # 마지막으로 active_connections에서 제거 (중복 제거 방지)
            if websocket in toss_manager.active_connections:
                toss_manager.active_connections.discard(websocket)
                logger.info(f"⚡ finally에서 active_connections에서 제거 - Client: {client_id}")
            
            # ConnectionManager를 통한 정리
            await toss_manager.disconnect(websocket, client_id)
            
            if db is not None:
                db.close()
            
            logger.info(f"✅ Toss WebSocket 종료 처리 완료 - Client: {client_id}")
    else:
        # stock_code가 없으면 단순 에코 모드
        try:
            await websocket.send_text("Toss WebSocket Connected! Send me a stock_code.")
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        except WebSocketDisconnect:
            await toss_manager.disconnect(websocket, client_id)


@router.get("/toss-ws/status")
async def get_toss_ws_status():
    """Toss WebSocket 연결 상태 조회"""
    return {
        "active_connections": len(toss_manager.active_connections),
        "total_clients": len(toss_manager.client_subscriptions),
        "subscribed_stocks": list(toss_manager.stock_subscribers.keys()),
        "stock_subscriber_count": {
            stock: len(clients) for stock, clients in toss_manager.stock_subscribers.items()
        }
    }


@router.post("/toss-ws/broadcast/{stock_code}")
async def broadcast_to_stock_subscribers(stock_code: str, message: dict):
    """특정 주식 구독자들에게 메시지 브로드캐스트 (테스트용)"""
    if stock_code not in toss_manager.stock_subscribers:
        return {"message": f"No subscribers for stock {stock_code}"}
    
    client_ids = toss_manager.stock_subscribers[stock_code]
    broadcast_message = {
        "type": "broadcast",
        "stock_code": stock_code,
        "data": message,
        "timestamp": time.time()
    }
    
    success_count = 0
    for websocket in toss_manager.active_connections:
        if str(id(websocket)) in client_ids:
            try:
                await websocket.send_text(json.dumps(broadcast_message))
                success_count += 1
            except Exception as e:
                logger.error(f"❌ 브로드캐스트 실패 - WebSocket: {id(websocket)}, Error: {e}")
    
    return {
        "message": f"Broadcasted to {success_count} subscribers of {stock_code}",
        "total_subscribers": len(client_ids),
        "success_count": success_count
    }
