from typing import Set, Dict, Optional
import asyncio
import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.config.db import SessionLocal
from app.db.models.user import User
from app.services.kis_shared_provider import SharedKisWebSocketProvider
from app.config import config
from websockets.exceptions import ConnectionClosed


router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        # 공유 KIS Provider (싱글톤)
        self._shared_kis_provider: Optional[SharedKisWebSocketProvider] = None
        self._client_subscriptions: Dict[str, Set[str]] = {}  # {client_id: {stock_ids}}

    async def connect(self, websocket: WebSocket):
        print(f"🔌 웹소켓 연결 시도 - ID: {id(websocket)}")
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"✅ 사용자 웹소켓 연결 완료 - ID: {id(websocket)}, 총 연결: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        print(f"🔴 웹소켓 disconnect 호출됨 - ID: {id(websocket)}")
        
        # 1. 즉시 active_connections에서 제거
        if websocket in self.active_connections:
            self.active_connections.discard(websocket)
            print(f"✅ active_connections에서 제거됨 - ID: {id(websocket)}, 남은 연결: {len(self.active_connections)}")
        else:
            print(f"⚠️ 웹소켓이 이미 active_connections에 없음 - ID: {id(websocket)}")
        
        # 2. 공유 provider에서 구독 제거
        await self._remove_shared_subscription(str(id(websocket)))
        
        print(f"✅ 사용자 웹소켓 연결 해제 완료. 총 연결: {len(self.active_connections)}")
    
    async def get_or_create_shared_provider(self, app_key: str, app_secret: str, approval_key: str) -> SharedKisWebSocketProvider:
        """공유 KIS Provider 가져오기 또는 생성"""
        # 기존 provider가 종료되었거나 없는 경우 새로 생성
        if (self._shared_kis_provider is None or 
            getattr(self._shared_kis_provider, '_should_close', True) or
            not getattr(self._shared_kis_provider, '_is_connected', False)):
            
            print("🚀 새로운 공유 KIS Provider 생성")
            self._shared_kis_provider = SharedKisWebSocketProvider(app_key, app_secret, approval_key)
            await self._shared_kis_provider.connect()
            print("✅ 공유 KIS Provider 연결 시작됨")
        else:
            print("♻️ 기존 공유 KIS Provider 재사용")
        
        return self._shared_kis_provider
    
    async def add_shared_subscription(self, client_id: str, stock_id: str, websocket: WebSocket) -> bool:
        """공유 provider에 구독 추가"""
        try:
            if self._shared_kis_provider is None:
                print("❌ 공유 provider가 초기화되지 않음")
                return False
            
            # 데이터 콜백 함수 생성 (웹소켓 상태 확인 포함)
            async def data_callback(stock_id: str, data: dict):
                # 웹소켓이 active_connections에 있는지 먼저 확인
                if websocket not in manager.active_connections:
                    print(f"⚠️ 웹소켓이 이미 제거됨 - Client: {client_id}, 전송 건너뛰기")
                    raise ConnectionError(f"WebSocket already removed for client {client_id}")
                
                try:
                    # 실시간 데이터를 웹소켓으로 전송
                    message = {
                        "stock_id": stock_id,
                        "data": data,
                        "timestamp": time.time()
                    }
                    await websocket.send_text(json.dumps(message))
                    # print(f"✅ 콜백 데이터 전송 성공 - Client: {client_id}, Stock: {stock_id}")  # 너무 많은 로그 방지
                except Exception as e:
                    print(f"❌ 콜백 데이터 전송 실패 - Client: {client_id}, Stock: {stock_id}, Error: {e}")
                    # 웹소켓 에러 발생 시 해당 클라이언트를 제거하기 위해 예외 재발생
                    raise e
            
            # TR_ID는 종목에 따라 결정
            if stock_id.startswith(('DNAS', 'RBAQ', 'RBAQU')):  # 미국 주식
                tr_id = "HDFSCNT0"  # 해외 체결 데이터
            else:  # 한국 주식
                tr_id = "H0STCNT0"  # 국내 체결 데이터
            
            print(f"📊 종목별 TR_ID 설정 - Stock: {stock_id}, TR_ID: {tr_id}")
            
            await self._shared_kis_provider.add_subscription(client_id, stock_id, tr_id, data_callback)
            
            # 클라이언트 구독 기록
            if client_id not in self._client_subscriptions:
                self._client_subscriptions[client_id] = set()
            self._client_subscriptions[client_id].add(stock_id)
            
            print(f"✅ 공유 구독 추가 완료 - Client: {client_id}, Stock: {stock_id}")
            return True
            
        except Exception as e:
            print(f"❌ 공유 구독 추가 실패 - Client: {client_id}, Error: {e}")
            return False
    
    async def _remove_shared_subscription(self, client_id: str):
        """클라이언트의 모든 공유 구독 제거"""
        try:
            if self._shared_kis_provider and client_id in self._client_subscriptions:
                await self._shared_kis_provider.remove_subscription(client_id)
                del self._client_subscriptions[client_id]
                print(f"✅ 공유 구독 제거 완료 - Client: {client_id}")
                
                # 모든 클라이언트가 제거되면 shared provider도 제거
                if not self._client_subscriptions:
                    print("🔄 모든 클라이언트 제거됨, 공유 Provider 정리")
                    self._shared_kis_provider = None
                    
        except Exception as e:
            print(f"❌ 공유 구독 제거 실패 - Client: {client_id}, Error: {e}")


manager = ConnectionManager()


@router.websocket("/kis-ws")
async def websocket_endpoint(websocket: WebSocket):
    # 파라미터 수신
    stock_id = websocket.query_params.get("stock_id")
    user_id = websocket.query_params.get("user_id")
    client_id = str(id(websocket))  # 클라이언트 ID로 웹소켓 ID 사용
    
    print(f"🌟 새로운 웹소켓 연결 요청 - Client: {client_id}, stock_id: {stock_id}, user_id: {user_id}")
    
    await manager.connect(websocket)

    # stock_id가 있는 경우: 공유 KIS Provider 사용
    if stock_id:
        db: Session | None = None
        
        try:
            # 사용자 기반 KIS 설정 로드
            db = SessionLocal()
            
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                
                # 우선순위: 사용자 설정 > 글로벌 설정(config)
                app_key = getattr(user, 'kis_app_key', None) or (config.KIS_APP_KEY or None)
                app_secret = getattr(user, 'kis_app_secret', None) or (config.KIS_APP_SECRET or None)
                
                if app_key and app_secret:
                    print(f"🔑 KIS 인증 정보 확인 완료 - Client: {client_id}")
                    
                    # 하드코딩된 approval key 사용 (임시)
                    approval = "5a9b6075-e42e-4548-9b63-0f6ecf006fb7"
                    
                    # 공유 Provider 가져오기 또는 생성
                    await manager.get_or_create_shared_provider(app_key, app_secret, approval)
                    
                    # 공유 구독 추가
                    success = await manager.add_shared_subscription(client_id, stock_id, websocket)
                    
                    if success:
                        print(f"✅ 공유 KIS 구독 성공 - Client: {client_id}, Stock: {stock_id}")
                        
                        # 연결 성공 메시지 전송
                        success_msg = {
                            "type": "connection_success",
                            "stock_id": stock_id,
                            "message": f"KIS 실시간 데이터 구독이 시작되었습니다.",
                            "client_id": client_id
                        }
                        await websocket.send_text(json.dumps(success_msg))
                        
                        # 무한 대기 (데이터는 콜백을 통해 전송됨)
                        try:
                            ping_count = 0
                            while websocket in manager.active_connections:
                                # 주기적으로 연결 상태 확인 (10초마다, 더 짧게)
                                await asyncio.sleep(10)
                                ping_count += 1
                                
                                try:
                                    # 연결 확인 ping 전송
                                    ping_msg = {
                                        "type": "ping",
                                        "timestamp": time.time(),
                                        "count": ping_count
                                    }
                                    await websocket.send_text(json.dumps(ping_msg))
                                    print(f"📡 연결 확인 ping 전송 #{ping_count} - Client: {client_id}")
                                    
                                except Exception as ping_e:
                                    print(f"❌ 연결 확인 ping 전송 실패 - Client: {client_id}, Error: {ping_e}")
                                    print(f"🔴 연결이 끊어진 것으로 판단, 루프 종료 - Client: {client_id}")
                                    # 연결이 끊어진 것으로 판단하고 루프 종료
                                    break
                                
                        except Exception as e:
                            print(f"❌ 연결 유지 중 오류 - Client: {client_id}, Error: {e}")
                            # 오류 발생 시 루프 종료
                    else:
                        # 구독 실패 메시지
                        error_msg = {
                            "type": "error",
                            "message": "KIS API 구독에 실패했습니다.",
                            "code": "SUBSCRIPTION_FAILED"
                        }
                        await websocket.send_text(json.dumps(error_msg))
                else:
                    # 인증 정보 없음
                    error_msg = {
                        "type": "error",
                        "message": "KIS API 인증 정보가 없습니다.",
                        "code": "AUTH_INFO_MISSING"
                    }
                    await websocket.send_text(json.dumps(error_msg))
            else:
                # 사용자 ID 없음
                error_msg = {
                    "type": "error",
                    "message": "사용자 ID가 필요합니다.",
                    "code": "USER_ID_MISSING"
                }
                await websocket.send_text(json.dumps(error_msg))
                
        except WebSocketDisconnect as e:
            print(f"🔴 웹소켓 연결 해제 감지 - Client: {client_id}, Code: {e.code}")
        except ConnectionClosed as e:
            print(f"🔴 웹소켓 연결 닫힘 감지 - Client: {client_id}, Code: {e.code}")
        except Exception as e:
            print(f"❌ 웹소켓 에러 발생 - Client: {client_id}, Error: {e}")
            try:
                error_msg = {
                    "type": "error",
                    "message": f"서버 오류가 발생했습니다: {str(e)}",
                    "code": "SERVER_ERROR"
                }
                await websocket.send_text(json.dumps(error_msg))
            except Exception as send_e:
                print(f"⚠️ 에러 메시지 전송 실패 - Client: {client_id}, Error: {send_e}")
        finally:
            print(f"🔄 웹소켓 정리 시작 - Client: {client_id}")
            
            # 즉시 active_connections에서 제거하여 더 이상 데이터가 전송되지 않도록 함
            if websocket in manager.active_connections:
                manager.active_connections.discard(websocket)
                print(f"⚡ 즉시 active_connections에서 제거 - Client: {client_id}")
            
            # ConnectionManager를 통한 정리 (공유 구독 제거 포함)
            await manager.disconnect(websocket)
            
            if db is not None:
                db.close()
            
            print(f"✅ 웹소켓 종료 처리 완료 - Client: {client_id}")
    else:
        # stock_id가 없으면 단순 에코 모드
        try:
            await websocket.send_text("Connected! Send me a message.")
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        except WebSocketDisconnect:
            await manager.disconnect(websocket)