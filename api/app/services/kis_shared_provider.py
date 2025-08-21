"""
KIS 웹소켓 공유 Provider
여러 클라이언트가 하나의 KIS 웹소켓 연결을 공유하여 사용
"""
import asyncio
import json
from typing import Dict, Set, Optional, Callable
from collections import defaultdict
import websockets
from dataclasses import dataclass
import time


@dataclass
class Subscription:
    """구독 정보"""
    stock_id: str
    tr_id: str
    subscribers: Set[str]  # client_ids


class SharedKisWebSocketProvider:
    """공유 KIS 웹소켓 Provider"""
    
    def __init__(self, app_key: str, app_secret: str, approval_key: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.approval_key = approval_key
        
        # 연결 상태
        self._ws_connection = None
        self._is_connected = False
        self._should_close = False
        
        # 구독 관리
        self._subscriptions: Dict[str, Subscription] = {}  # {stock_id: Subscription}
        self._client_stocks: Dict[str, Set[str]] = defaultdict(set)  # {client_id: {stock_ids}}
        self._data_callbacks: Dict[str, Callable] = {}  # {client_id: callback}
        
        # 연결 태스크
        self._connection_task = None
        self._lock = asyncio.Lock()
        
        # 모의 데이터 생성을 위한 태스크
        # 모의 데이터 기능 완전 제거됨
    
    async def add_subscription(self, client_id: str, stock_id: str, tr_id: str, callback: Callable):
        """클라이언트의 종목 구독 추가"""
        async with self._lock:
            print(f"📌 구독 추가 요청 - Client: {client_id}, Stock: {stock_id}")
            
            # 콜백 등록
            self._data_callbacks[client_id] = callback
            
            # 이미 구독 중인 종목인 경우
            if stock_id in self._subscriptions:
                self._subscriptions[stock_id].subscribers.add(client_id)
                self._client_stocks[client_id].add(stock_id)
                print(f"✅ 기존 구독에 추가 - Stock: {stock_id}, 총 구독자: {len(self._subscriptions[stock_id].subscribers)}")
                return
            
            # 새로운 종목 구독
            self._subscriptions[stock_id] = Subscription(
                stock_id=stock_id,
                tr_id=tr_id,
                subscribers={client_id}
            )
            self._client_stocks[client_id].add(stock_id)
            
            # KIS에 구독 요청
            if self._is_connected and self._ws_connection:
                await self._subscribe_to_kis(stock_id, tr_id)
            
            print(f"✅ 새로운 구독 생성 - Stock: {stock_id}")
    
    async def remove_subscription(self, client_id: str, stock_id: Optional[str] = None):
        """클라이언트의 종목 구독 제거"""
        async with self._lock:
            print(f"📌 구독 제거 요청 - Client: {client_id}, Stock: {stock_id or '전체'}")
            
            # 특정 종목만 제거
            if stock_id:
                if stock_id in self._subscriptions:
                    self._subscriptions[stock_id].subscribers.discard(client_id)
                    
                    # 구독자가 없으면 종목 구독 해제
                    if not self._subscriptions[stock_id].subscribers:
                        tr_id = self._subscriptions[stock_id].tr_id
                        print(f"🔴 종목 구독자 없음, KIS 구독 해제 요청 - Stock: {stock_id}")
                        
                        # KIS에서 구독 해제
                        if self._is_connected and self._ws_connection:
                            await self._unsubscribe_from_kis(stock_id, tr_id)
                        
                        del self._subscriptions[stock_id]
                        print(f"✅ 종목 구독 완전 해제 - Stock: {stock_id}")
                
                self._client_stocks[client_id].discard(stock_id)
            
            # 클라이언트의 모든 구독 제거
            else:
                if client_id in self._client_stocks:
                    stocks_to_remove = list(self._client_stocks[client_id])
                    print(f"🔄 클라이언트 모든 구독 제거 시작 - Client: {client_id}, Stocks: {stocks_to_remove}")
                    
                    # 재귀 호출 대신 직접 처리로 무한 루프 방지
                    for stock in stocks_to_remove:
                        if stock in self._subscriptions:
                            self._subscriptions[stock].subscribers.discard(client_id)
                            
                            # 구독자가 없으면 종목 구독 해제
                            if not self._subscriptions[stock].subscribers:
                                tr_id = self._subscriptions[stock].tr_id
                                print(f"🔴 종목 구독자 없음, KIS 구독 해제 요청 - Stock: {stock}")
                                
                                # KIS에서 구독 해제
                                if self._is_connected and self._ws_connection:
                                    await self._unsubscribe_from_kis(stock, tr_id)
                                
                                del self._subscriptions[stock]
                                print(f"✅ 종목 구독 완전 해제 - Stock: {stock}")
                    
                    # 클라이언트 데이터 정리
                    self._data_callbacks.pop(client_id, None)
                    if client_id in self._client_stocks:
                        del self._client_stocks[client_id]
                    
                    print(f"✅ 클라이언트 모든 구독 제거 완료 - Client: {client_id}")
            
            # 모든 구독이 제거되었으면 KIS 연결 종료
            if not self._subscriptions and not self._client_stocks:
                print("🔴 모든 구독이 제거됨, KIS 연결 종료 시작")
                await self._shutdown_connection()
    
    async def _shutdown_connection(self):
        """KIS 연결 완전 종료"""
        print("🔴 KIS 연결 완전 종료 시작")
        self._should_close = True
        
        # 모의 데이터 태스크 제거됨
        
        # KIS 웹소켓 연결 종료
        if self._ws_connection:
            try:
                await self._ws_connection.close()
                print("✅ KIS 웹소켓 연결 종료 완료")
            except Exception as e:
                print(f"❌ KIS 웹소켓 종료 중 오류: {e}")
        
        self._ws_connection = None
        self._is_connected = False
        
        # 연결 관리 태스크 종료
        if self._connection_task and not self._connection_task.done():
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            print("✅ 연결 관리 태스크 종료 완료")
        
        print("✅ KIS 연결 완전 종료 완료")
    
    async def _subscribe_to_kis(self, stock_id: str, tr_id: str):
        """KIS에 종목 구독 요청"""
        if not self._ws_connection:
            return
            
        subscribe_msg = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",  # 구독
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": stock_id
                }
            }
        }
        
        await self._ws_connection.send(json.dumps(subscribe_msg))
        print(f"📤 KIS 구독 요청 전송 - Stock: {stock_id}, TR_ID: {tr_id}")
    
    async def _unsubscribe_from_kis(self, stock_id: str, tr_id: str):
        """KIS에서 종목 구독 해제"""
        if not self._ws_connection:
            return
            
        unsubscribe_msg = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "2",  # 구독 해제
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": stock_id
                }
            }
        }
        
        await self._ws_connection.send(json.dumps(unsubscribe_msg))
        print(f"📤 KIS 구독 해제 요청 전송 - Stock: {stock_id}, TR_ID: {tr_id}")
    
    async def connect(self):
        """KIS 웹소켓 연결 시작"""
        if self._connection_task and not self._connection_task.done():
            print("⚠️ KIS 연결이 이미 진행 중")
            return
        
        self._connection_task = asyncio.create_task(self._maintain_connection())
        
        # 모의 데이터 생성 기능 제거됨
        
        print("🚀 KIS 공유 연결 태스크 시작")
    
    async def _maintain_connection(self):
        """KIS 웹소켓 연결 유지"""
        while not self._should_close:
            try:
                print("🔄 KIS 웹소켓 연결 시도...")
                async with websockets.connect(
                    'ws://ops.koreainvestment.com:21000',
                    ping_interval=30,
                    ping_timeout=10
                ) as websocket:
                    self._ws_connection = websocket
                    self._is_connected = True
                    print("✅ KIS 웹소켓 연결 성공")
                    
                    # 기존 구독 모두 재등록
                    async with self._lock:
                        for stock_id, subscription in self._subscriptions.items():
                            await self._subscribe_to_kis(stock_id, subscription.tr_id)
                    
                    # 메시지 수신 루프
                    async for message in websocket:
                        if self._should_close:
                            break
                        
                        await self._process_message(message)
                        
            except Exception as e:
                print(f"❌ KIS 웹소켓 오류: {e}")
                self._is_connected = False
                
                if not self._should_close:
                    print("⏳ 5초 후 재연결 시도...")
                    await asyncio.sleep(5)
    
    async def _process_message(self, message: str):
        """KIS 메시지 처리 및 구독자에게 전달"""
        try:
            # 모든 메시지 로그 출력 (디버깅용)
            print(f"📨 KIS 메시지 수신: {message[:100]}..." if len(message) > 100 else f"📨 KIS 메시지 수신: {message}")
            
            # JSON 형식이 아닌 경우 (실시간 데이터는 문자열일 수 있음)
            if not message.startswith('{'):
                print(f"📊 실시간 데이터 수신 (비JSON): {message}")
                # 실시간 데이터 파싱 시도
                await self._process_realtime_data(message)
                return
            
            data = json.loads(message)
            
            # PINGPONG 처리
            if data.get("header", {}).get("tr_id") == "PINGPONG":
                await self._ws_connection.pong(message)
                print(f"🏓 PINGPONG 응답 전송됨")
                return
            
            # 구독 확인 메시지 (HDFSCNT0)
            tr_id = data.get("header", {}).get("tr_id")
            if tr_id == "HDFSCNT0":
                print(f"✅ 구독 확인 메시지 수신: {data}")
                return
            
            # 실시간 데이터 파싱
            stock_id = self._extract_stock_id(data)
            print(f"🔍 종목 ID 추출 결과: {stock_id}")
            
            if stock_id and stock_id in self._subscriptions:
                print(f"📈 실시간 데이터 전달 시작 - Stock: {stock_id}, 구독자: {len(self._subscriptions[stock_id].subscribers)}")
                
                # 구독자들에게 데이터 전달 - 즉시 끊어진 연결 제거
                subscription = self._subscriptions[stock_id]
                clients_to_remove = []
                
                for client_id in list(subscription.subscribers):  # 복사본 사용
                    if client_id in self._data_callbacks:
                        try:
                            await self._data_callbacks[client_id](stock_id, data)
                            # print(f"📤 데이터 전송 완료 - Client: {client_id}")  # 로그 양 줄이기
                        except Exception as e:
                            print(f"❌ 데이터 전송 실패 - Client: {client_id}, Error: {e}")
                            print(f"🔴 연결 끊어진 클라이언트 즉시 제거 - Client: {client_id}")
                            clients_to_remove.append(client_id)
                            
                            # 즉시 구독에서 제거하여 더 이상 처리하지 않도록
                            subscription.subscribers.discard(client_id)
                
                # 연결 끊어진 클라이언트들 완전 정리
                if clients_to_remove:
                    print(f"🧹 연결 끊어진 클라이언트들 완전 정리 - Clients: {clients_to_remove}")
                    for client_id in clients_to_remove:
                        # 클라이언트 데이터 완전 정리
                        self._data_callbacks.pop(client_id, None)
                        if client_id in self._client_stocks:
                            del self._client_stocks[client_id]
                        print(f"✅ 클라이언트 완전 제거 - Client: {client_id}")
                
                # 구독자가 모두 제거되었다면 종목 자체를 구독 해제
                if not subscription.subscribers:
                    print(f"🔴 구독자 모두 제거됨, 종목 구독 해제 - Stock: {stock_id}")
                    tr_id = subscription.tr_id
                    if self._is_connected and self._ws_connection:
                        await self._unsubscribe_from_kis(stock_id, tr_id)
                    del self._subscriptions[stock_id]
                
                # 모든 구독이 제거되었다면 KIS 연결 종료
                if not self._subscriptions and not self._client_stocks:
                    print("🔴 모든 구독이 제거됨, KIS 연결 종료 시작")
                    await self._shutdown_connection()
                        
            else:
                print(f"⚠️ 구독 없음 또는 종목 ID 없음 - Stock: {stock_id}, 등록된 구독: {list(self._subscriptions.keys())}")
                        
        except Exception as e:
            print(f"❌ 메시지 처리 오류: {e}")
            print(f"❌ 원본 메시지: {message}")
    
    async def _process_realtime_data(self, message: str):
        """실시간 데이터 처리 (문자열 형식)"""
        try:
            # KIS 실시간 데이터는 파이프(|) 구분자를 사용할 수 있음
            if '|' in message:
                parts = message.split('|')
                print(f"📊 파이프 구분 실시간 데이터: {parts}")
                
                # 종목 코드가 포함된 부분을 찾아 구독자에게 전달
                for stock_id in self._subscriptions.keys():
                    if any(stock_id in part for part in parts):
                        print(f"📈 실시간 데이터 매칭 - Stock: {stock_id}")
                        
                        subscription = self._subscriptions[stock_id]
                        
                        # 실시간으로 연결 끊어진 클라이언트 감지 및 제거
                        clients_to_remove = []
                        
                        for client_id in list(subscription.subscribers):  # 복사본 사용
                            if client_id in self._data_callbacks:
                                try:
                                    # 원시 데이터를 JSON 형식으로 래핑
                                    wrapped_data = {
                                        "type": "realtime_data",
                                        "raw_message": message,
                                        "parts": parts
                                    }
                                    await self._data_callbacks[client_id](stock_id, wrapped_data)
                                    # print(f"📤 실시간 데이터 전송 완료 - Client: {client_id}")  # 로그 양 줄이기
                                except Exception as e:
                                    print(f"❌ 실시간 데이터 콜백 오류 - Client: {client_id}, Error: {e}")
                                    print(f"🔴 연결 끊어진 클라이언트 즉시 제거 - Client: {client_id}")
                                    clients_to_remove.append(client_id)
                                    
                                    # 즉시 구독에서 제거하여 더 이상 처리하지 않도록
                                    subscription.subscribers.discard(client_id)
                        
                        # 연결 끊어진 클라이언트들 완전 정리
                        if clients_to_remove:
                            print(f"🧹 연결 끊어진 클라이언트들 완전 정리 - Clients: {clients_to_remove}")
                            for client_id in clients_to_remove:
                                # 클라이언트 데이터 완전 정리
                                self._data_callbacks.pop(client_id, None)
                                if client_id in self._client_stocks:
                                    del self._client_stocks[client_id]
                                print(f"✅ 클라이언트 완전 제거 - Client: {client_id}")
                        
                        # 구독자가 모두 제거되었다면 종목 자체를 구독 해제
                        if not subscription.subscribers:
                            print(f"🔴 구독자 모두 제거됨, 종목 구독 해제 - Stock: {stock_id}")
                            tr_id = subscription.tr_id
                            if self._is_connected and self._ws_connection:
                                await self._unsubscribe_from_kis(stock_id, tr_id)
                            del self._subscriptions[stock_id]
                        
                        # 모든 구독이 제거되었다면 KIS 연결 종료
                        if not self._subscriptions and not self._client_stocks:
                            print("🔴 모든 구독이 제거됨, KIS 연결 종료 시작")
                            await self._shutdown_connection()
                        
                        return
            
            print(f"⚠️ 처리할 수 없는 실시간 데이터 형식: {message}")
        except Exception as e:
            print(f"❌ 실시간 데이터 처리 오류: {e}")
    
    def _extract_stock_id(self, data: Dict) -> Optional[str]:
        """메시지에서 종목 ID 추출"""
        try:
            if isinstance(data, dict):
                # header에서 tr_key 추출 (종목 코드)
                header = data.get("header", {})
                if isinstance(header, dict):
                    tr_key = header.get("tr_key")
                    if tr_key:
                        print(f"🔍 header.tr_key에서 추출: {tr_key}")
                        return tr_key
                
                # body에서 추출 시도
                body = data.get("body", {})
                if isinstance(body, dict):
                    extracted = body.get("stock_id") or body.get("symbol") or body.get("code")
                    if extracted:
                        print(f"🔍 body에서 추출: {extracted}")
                        return extracted
                
            print(f"⚠️ 종목 ID 추출 실패 - 데이터 구조: {data}")
            return None
        except Exception as e:
            print(f"⚠️ 종목 ID 추출 중 오류: {e}")
            return None
    
    # _generate_mock_data 메서드 완전 제거됨 - 불필요한 가짜 데이터 생성 방지
    
    async def close(self):
        """연결 종료"""
        print("🔴 KIS 공유 연결 종료 요청")
        self._should_close = True
        
        # 모의 데이터 태스크 제거됨
        
        if self._ws_connection:
            await self._ws_connection.close()
        
        if self._connection_task:
            await self._connection_task
