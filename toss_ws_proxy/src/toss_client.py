"""
Toss WebSocket Client for Proxy Service
기존 TossWebSocketClient를 기반으로 프록시 서비스용으로 개선
"""
import asyncio
import websockets
import logging
import requests
import time
import uuid
import json
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from .config import config
from .models import (
    STOMPFrame, ConnectionStatus, TossAuthInfo, 
    ConnectionInfo, MessageType, ProxyMessage
)


class TossWebSocketProxy:
    """Toss WebSocket 프록시 클라이언트"""
    
    def __init__(self, message_handler: Optional[Callable] = None):
        self.url = config.websocket_url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connection_info = ConnectionInfo(status=ConnectionStatus.DISCONNECTED)
        self.auth_info = TossAuthInfo(cookies=config.default_cookies.copy())
        self.connection_id = str(uuid.uuid4())
        
        # 메시지 처리
        self.message_handler = message_handler
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_message_queue_size)
        
        # 비동기 태스크 관리
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.listen_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # 로깅 설정
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format=config.log_format
        )
        self.logger = logging.getLogger(__name__)

    # =============================================================================
    # 인증 및 토큰 관리
    # =============================================================================
    
    async def fetch_authorization_token(self) -> bool:
        """Toss API에서 Authorization 토큰을 가져옵니다"""
        try:
            self.logger.info("🔑 Fetching authorization token from Toss API...")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "accept": "application/json",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "App-Version": "2025-08-26 19:36:15",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Host": "wts-api.tossinvest.com",
                "Origin": "https://www.tossinvest.com",
                "Pragma": "no-cache",
                "Referer": "https://www.tossinvest.com/stocks/A005930/analytics",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "browser-tab-id": f"browser-tab-{self.connection_id[:32]}",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"'
            }
            
            response = requests.get(
                config.refresh_token_url, 
                cookies=self.auth_info.cookies, 
                headers=headers, 
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    self.auth_info.authorization = data['result']
                    self.auth_info.expires_at = datetime.now() + timedelta(hours=1)
                    self.logger.info("✅ Authorization token fetched successfully")
                    
                    # UTK 쿠키 추출
                    for cookie in response.cookies:
                        if cookie.name == 'UTK':
                            self.auth_info.cookies['UTK'] = cookie.value
                            self.auth_info.utk_token = cookie.value
                            break
                    
                    return True
                else:
                    self.logger.error(f"❌ Invalid response format: {data}")
                    return False
            else:
                self.logger.error(f"❌ Failed to fetch token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Token fetch error: {e}")
            return False

    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """사용자 정의 쿠키 업데이트"""
        self.auth_info.cookies.update(cookies)
        self.logger.info(f"🍪 Updated cookies: {list(cookies.keys())}")

    # =============================================================================
    # STOMP 프로토콜 처리
    # =============================================================================
    
    def _create_stomp_frame(self, command: str, headers: Dict[str, str] = None, body: str = "") -> str:
        """STOMP 프레임 생성"""
        frame = f"{command}\n"
        
        if headers:
            for key, value in headers.items():
                frame += f"{key}:{value}\n"
        
        frame += "\n"  # 헤더와 바디 사이 빈 줄
        
        if body:
            frame += f"{body}\n"
        
        frame += "\x00"  # null byte로 종료
        return frame
    
    def _parse_stomp_frame(self, data: str) -> STOMPFrame:
        """STOMP 프레임 파싱"""
        lines = data.split('\n')
        command = lines[0]
        headers = {}
        body_start = -1
        
        for i, line in enumerate(lines[1:], 1):
            if line == '':
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key] = value
        
        body = '\n'.join(lines[body_start:]) if body_start > 0 else ""
        body = body.rstrip('\x00')  # null 문자 제거
        
        return STOMPFrame(command=command, headers=headers, body=body)

    # =============================================================================
    # WebSocket 연결 관리
    # =============================================================================
    
    async def connect(self) -> bool:
        """WebSocket 연결 및 STOMP 핸드셰이크"""
        try:
            self.connection_info.status = ConnectionStatus.CONNECTING
            
            # 토큰 확인 및 갱신
            if not self.auth_info.authorization or self._token_expired():
                self.logger.info("🔄 Authorization token expired or not set, fetching from API...")
                if not await self.fetch_authorization_token():
                    self.logger.error("❌ Failed to fetch authorization token")
                    self.connection_info.status = ConnectionStatus.FAILED
                    return False
            
            self.logger.info(f"📡 Connecting to {self.url}")
            
            # WebSocket 연결
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "Origin": "https://www.tossinvest.com",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache"
            }
            
            self.websocket = await websockets.connect(
                self.url, 
                additional_headers=headers,
                subprotocols=["v12.stomp", "v11.stomp", "v10.stomp"],
                compression="deflate",
                open_timeout=config.connection_timeout
            )
            
            # STOMP CONNECT 프레임 전송
            connect_headers = {
                "device-id": config.device_id,
                "connection-id": self.connection_id,
                "authorization": self.auth_info.authorization,
                "accept-version": "1.2,1.1,1.0",
                "heart-beat": f"{int(config.heartbeat_interval * 1000)},{int(config.heartbeat_interval * 1000)}"
            }
            
            connect_frame = self._create_stomp_frame("CONNECT", connect_headers)
            await self.websocket.send(connect_frame)
            
            # CONNECTED 응답 대기
            response = await self.websocket.recv()
            parsed_response = self._parse_stomp_frame(response)
            
            if parsed_response.command == 'CONNECTED':
                self.connection_info.status = ConnectionStatus.CONNECTED
                self.connection_info.connected_at = datetime.now()
                self.connection_info.reconnect_attempts = 0
                self.logger.info("✅ Successfully connected to Toss WebSocket")
                
                # Heartbeat 및 메시지 리스닝 시작
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self.listen_task = asyncio.create_task(self._listen_loop())
                return True
            else:
                self.logger.error(f"❌ Failed to connect: {parsed_response}")
                self.connection_info.status = ConnectionStatus.FAILED
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.connection_info.status = ConnectionStatus.FAILED
            return False
    
    def _token_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        if not self.auth_info.expires_at:
            return True
        return datetime.now() >= self.auth_info.expires_at - timedelta(minutes=5)  # 5분 여유
    
    async def disconnect(self) -> None:
        """연결 해제"""
        self.logger.info("🔌 Disconnecting from WebSocket...")
        self.connection_info.status = ConnectionStatus.DISCONNECTED
        
        # 태스크 정리
        await self._cleanup_tasks()
        
        if self.websocket:
            try:
                disconnect_frame = self._create_stomp_frame("DISCONNECT")
                await self.websocket.send(disconnect_frame)
                await self.websocket.close()
                self.logger.info("🧹 Disconnected from WebSocket")
            except Exception as e:
                self.logger.error(f"❌ Disconnect error: {e}")
            finally:
                self.websocket = None
                
        self.connection_info.active_subscriptions.clear()
    
    async def _cleanup_tasks(self) -> None:
        """비동기 태스크 정리"""
        tasks = [self.heartbeat_task, self.listen_task, self.reconnect_task]
        
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.heartbeat_task = None
        self.listen_task = None
        self.reconnect_task = None

    # =============================================================================
    # Heartbeat 및 자동 재연결
    # =============================================================================
    
    async def _heartbeat_loop(self):
        """STOMP Heartbeat 루프 - 연결 유지"""
        try:
            while (self.connection_info.status == ConnectionStatus.CONNECTED and 
                   self.websocket):
                await asyncio.sleep(config.heartbeat_interval)
                
                if (self.connection_info.status == ConnectionStatus.CONNECTED and 
                    self.websocket):
                    await self.websocket.send("\n")  # Heartbeat 전송
                    self.connection_info.last_heartbeat = datetime.now()
                    
        except Exception as e:
            self.logger.warning(f"💓 Heartbeat loop error: {e}")
            await self._trigger_reconnect()
    
    async def _trigger_reconnect(self) -> None:
        """재연결 트리거"""
        if self.connection_info.status in [ConnectionStatus.RECONNECTING, ConnectionStatus.CONNECTING]:
            return  # 이미 재연결 중
            
        self.logger.info("🔄 Triggering reconnection...")
        self.connection_info.status = ConnectionStatus.RECONNECTING
        
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self._auto_reconnect())
    
    async def _auto_reconnect(self) -> None:
        """자동 재연결 루프"""
        while (self.connection_info.reconnect_attempts < config.max_reconnect_attempts and
               self.connection_info.status == ConnectionStatus.RECONNECTING):
            
            self.connection_info.reconnect_attempts += 1
            delay = config.reconnect_delay * (config.reconnect_backoff_multiplier ** (self.connection_info.reconnect_attempts - 1))
            
            self.logger.info(f"🔄 Reconnection attempt {self.connection_info.reconnect_attempts}/{config.max_reconnect_attempts} in {delay:.1f}s")
            await asyncio.sleep(delay)
            
            # 기존 연결 정리
            await self._cleanup_tasks()
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
            
            # 재연결 시도
            if await self.connect():
                self.logger.info("✅ Reconnection successful")
                
                # 기존 구독 복원
                await self._restore_subscriptions()
                return
            else:
                self.logger.warning(f"❌ Reconnection attempt {self.connection_info.reconnect_attempts} failed")
        
        # 최대 재연결 시도 횟수 초과
        if self.connection_info.reconnect_attempts >= config.max_reconnect_attempts:
            self.logger.error("❌ Max reconnection attempts reached. Service will restart.")
            self.connection_info.status = ConnectionStatus.FAILED
            # 여기서 프로세스 재시작 로직 추가 가능

    async def _restore_subscriptions(self) -> None:
        """기존 구독 복원"""
        for subscription_id, topic in self.connection_info.active_subscriptions.items():
            self.logger.info(f"🔄 Restoring subscription: {topic}")
            await self.subscribe(topic, subscription_id)

    # =============================================================================
    # 메시지 리스닝 및 처리
    # =============================================================================
    
    async def _listen_loop(self) -> None:
        """메시지 수신 루프"""
        try:
            while (self.connection_info.status == ConnectionStatus.CONNECTED and 
                   self.websocket):
                
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=config.heartbeat_interval * 2
                    )
                    parsed_message = self._parse_stomp_frame(message)
                    await self._handle_message(parsed_message)
                    
                except asyncio.TimeoutError:
                    self.logger.warning("⏰ Message receive timeout")
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("🔌 WebSocket connection closed")
            await self._trigger_reconnect()
        except Exception as e:
            self.logger.error(f"❌ Listen loop error: {e}")
            await self._trigger_reconnect()
    
    async def _handle_message(self, parsed_message: STOMPFrame) -> None:
        """메시지 처리 및 큐에 추가"""
        try:
            if parsed_message.command == 'MESSAGE':
                headers = parsed_message.headers
                subscription_id = headers.get('subscription', 'unknown')
                topic = self.connection_info.active_subscriptions.get(subscription_id, 'unknown')
                
                proxy_message = ProxyMessage(
                    message_type=MessageType.STOCK_TRADE,
                    timestamp=datetime.now(),
                    data={
                        'headers': headers,
                        'body': parsed_message.body
                    },
                    subscription_id=subscription_id,
                    topic=topic
                )
                
                # 메시지 큐에 추가 (논블로킹)
                try:
                    self.message_queue.put_nowait(proxy_message)
                except asyncio.QueueFull:
                    self.logger.warning("⚠️ Message queue is full, dropping oldest message")
                    try:
                        self.message_queue.get_nowait()  # 오래된 메시지 제거
                        self.message_queue.put_nowait(proxy_message)
                    except asyncio.QueueEmpty:
                        pass
                
                # 외부 메시지 핸들러 호출
                if self.message_handler:
                    try:
                        await self.message_handler(proxy_message)
                    except Exception as e:
                        self.logger.error(f"❌ Message handler error: {e}")
                        
        except Exception as e:
            self.logger.error(f"❌ Message handling error: {e}")

    # =============================================================================
    # 구독 관리
    # =============================================================================
    
    async def subscribe(self, topic: str, subscription_id: str = None) -> bool:
        """토픽 구독"""
        if self.connection_info.status != ConnectionStatus.CONNECTED or not self.websocket:
            self.logger.error("❌ Not connected to WebSocket")
            return False
        
        if subscription_id is None:
            subscription_id = str(abs(hash(topic)) % 10000)  # 토픽 기반 ID 생성
        
        try:
            subscribe_headers = {
                "id": subscription_id,
                "receipt": f"{subscription_id}-sub_receipt",
                "destination": topic
            }
            
            subscribe_frame = self._create_stomp_frame("SUBSCRIBE", subscribe_headers)
            await self.websocket.send(subscribe_frame)
            
            # 구독 정보 저장
            self.connection_info.active_subscriptions[subscription_id] = topic
            self.logger.info(f"✅ Subscribed to: {topic} (ID: {subscription_id})")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ Subscribe failed: {e}")
            return False
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """구독 해제"""
        if self.connection_info.status != ConnectionStatus.CONNECTED or not self.websocket:
            self.logger.error("❌ Not connected to WebSocket")
            return False
        
        try:
            unsubscribe_headers = {
                "id": subscription_id,
                "receipt": f"{subscription_id}-unsub_receipt"
            }
            
            unsubscribe_frame = self._create_stomp_frame("UNSUBSCRIBE", unsubscribe_headers)
            await self.websocket.send(unsubscribe_frame)
            
            # 구독 정보 제거
            topic = self.connection_info.active_subscriptions.pop(subscription_id, "unknown")
            self.logger.info(f"✅ Unsubscribed from: {topic} (ID: {subscription_id})")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ Unsubscribe failed: {e}")
            return False

    # =============================================================================
    # 상태 조회
    # =============================================================================
    
    def get_connection_status(self) -> ConnectionInfo:
        """연결 상태 조회"""
        return self.connection_info.copy()
    
    def get_active_subscriptions(self) -> Dict[str, str]:
        """활성 구독 목록 조회"""
        return self.connection_info.active_subscriptions.copy()
    
    async def get_message(self, timeout: Optional[float] = None) -> Optional[ProxyMessage]:
        """메시지 큐에서 메시지 가져오기"""
        try:
            if timeout:
                return await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
            else:
                return await self.message_queue.get()
        except asyncio.TimeoutError:
            return None
        except asyncio.QueueEmpty:
            return None
