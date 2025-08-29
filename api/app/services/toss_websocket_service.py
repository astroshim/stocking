"""
Toss WebSocket 서비스

FastAPI 백그라운드에서 실행되는 실시간 주식 데이터 수신 서비스
"""
import asyncio
import websockets
import logging
import requests
import time
import uuid
from typing import Optional, Dict, Any, List, Callable
import json


class TossWebSocketService:
    """Toss WebSocket STOMP 클라이언트 서비스"""
    
    def __init__(self):
        self.url = "wss://realtime-socket.tossinvest.com/ws"
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.device_id = "WTS-6857e1aa2ef34224a9ccfb6f879c1c1e"
        self.connection_id = str(uuid.uuid4())
        self.authorization: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.listen_task: Optional[asyncio.Task] = None
        
        # 구독할 토픽 목록
        self.subscriptions: List[str] = []
        
        # 메시지 핸들러들
        self.message_handlers: List[Callable[[Dict[str, Any]], None]] = []
        
        # Toss API 쿠키 설정
        self.cookies = {
            "x-toss-distribution-id": "59",
            "deviceId": "WTS-6857e1aa2ef34224a9ccfb6f879c1c1e",
            "XSRF-TOKEN": "3b1985f0-4433-49e0-9b1b-8920f350835a",
            "_browserId": "f827953e9801452da0996f717a9839f6",
            "BTK": "mOmOQulCKx9ku7NB6MKe8faF2shkD/4VKtmvVlchn18=",
            "SESSION": "M2QwYjBhNjQtYjJiNi00ZjM5LWE0MmEtZWI3YjliMGI0NjJk",
            "_gid": "GA1.2.1102199365.1756283030",
            "_ga_9XQG87E8PF": "GS2.2.s1756283030$o1$g0$t1756283030$j60$l0$h0",
            "_ga": "GA1.1.1271267878.1756275985",
            "_ga_T5907TQ00C": "GS2.1.s1756282450$o3$g1$t1756283803$j60$l0$h0"
        }
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)

    # =============================================================================
    # 서비스 생명주기 관리
    # =============================================================================
    
    async def start(self) -> bool:
        """WebSocket 서비스 시작"""
        try:
            self.logger.info("🚀 Starting Toss WebSocket Service...")
            self.is_running = True
            
            # 기본 구독 토픽 설정
            # self.add_subscription("/topic/v1/kr/stock/trade/A005930")  # 삼성전자
            
            # WebSocket 연결
            if await self._connect():
                # 구독 실행
                for topic in self.subscriptions:
                    await self._subscribe(topic)
                
                # 메시지 수신 시작
                self.listen_task = asyncio.create_task(self._listen_loop())
                
                self.logger.info("✅ Toss WebSocket Service started successfully")
                return True
            else:
                self.logger.error("❌ Failed to start Toss WebSocket Service")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error starting WebSocket service: {e}")
            return False
    
    async def stop(self) -> None:
        """WebSocket 서비스 중지"""
        try:
            self.logger.info("🛑 Stopping Toss WebSocket Service...")
            self.is_running = False
            
            # 리스닝 태스크 중지
            if self.listen_task:
                self.listen_task.cancel()
                try:
                    await self.listen_task
                except asyncio.CancelledError:
                    pass
                self.listen_task = None
            
            # WebSocket 연결 해제
            await self._disconnect()
            
            self.logger.info("✅ Toss WebSocket Service stopped")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping WebSocket service: {e}")

    # =============================================================================
    # 구독 관리
    # =============================================================================
    
    def add_subscription(self, topic: str) -> None:
        """구독 토픽 추가"""
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
            self.logger.info(f"📝 Added subscription: {topic}")
    
    def remove_subscription(self, topic: str) -> None:
        """구독 토픽 제거"""
        if topic in self.subscriptions:
            self.subscriptions.remove(topic)
            self.logger.info(f"🗑️ Removed subscription: {topic}")
    
    def add_message_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """메시지 핸들러 추가"""
        self.message_handlers.append(handler)
        self.logger.info(f"📨 Added message handler: {handler.__name__}")

    # =============================================================================
    # 인증 및 토큰 관리
    # =============================================================================
    
    def _fetch_authorization_token(self) -> bool:
        """Toss API에서 Authorization 토큰을 가져옵니다"""
        try:
            self.logger.info("🔑 Fetching authorization token from Toss API...")
            
            url = "https://wts-api.tossinvest.com/api/v1/refresh-utk"
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
            
            response = requests.get(url, cookies=self.cookies, headers=headers, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    self.authorization = data['result']
                    self.logger.info("✅ Authorization token fetched successfully")
                    
                    # UTK 쿠키도 추출
                    for cookie in response.cookies:
                        if cookie.name == 'UTK':
                            self.cookies['UTK'] = cookie.value
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
    
    def _parse_stomp_frame(self, data: str) -> Dict[str, Any]:
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
        
        return {
            'command': command,
            'headers': headers,
            'body': body
        }

    # =============================================================================
    # WebSocket 연결 관리
    # =============================================================================
    
    async def _connect(self) -> bool:
        """WebSocket 연결 및 STOMP 핸드셰이크"""
        try:
            # 토큰 가져오기
            if not self.authorization:
                if not self._fetch_authorization_token():
                    self.logger.error("❌ Failed to fetch authorization token")
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
                open_timeout=15.0
            )
            
            # STOMP CONNECT 프레임 전송
            connect_headers = {
                "device-id": self.device_id,
                "connection-id": self.connection_id,
                "authorization": self.authorization,
                "accept-version": "1.2,1.1,1.0",
                "heart-beat": "5000,5000"
            }
            
            connect_frame = self._create_stomp_frame("CONNECT", connect_headers)
            await self.websocket.send(connect_frame)
            
            # CONNECTED 응답 대기
            response = await self.websocket.recv()
            parsed_response = self._parse_stomp_frame(response)
            
            if parsed_response['command'] == 'CONNECTED':
                self.is_connected = True
                self.logger.info("✅ Successfully connected to Toss WebSocket")
                
                # Heartbeat 시작
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                return True
            else:
                self.logger.error(f"❌ Failed to connect: {parsed_response}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """WebSocket 재연결"""
        try:
            self.logger.info("🔄 Starting WebSocket reconnection...")
            
            # 기존 연결 정리
            await self._disconnect()
            
            # 새로운 연결 시도
            success = await self._connect()
            
            if success:
                # 기존 구독 목록 재구독
                if self.subscriptions:
                    self.logger.info(f"🔄 Re-subscribing to {len(self.subscriptions)} topics...")
                    failed_subscriptions = []
                    
                    for topic in self.subscriptions.copy():  # 복사본 사용
                        subscription_id = str(uuid.uuid4())
                        if not await self._subscribe(topic, subscription_id):
                            failed_subscriptions.append(topic)
                            self.logger.warning(f"⚠️ Failed to re-subscribe to {topic}")
                    
                    if failed_subscriptions:
                        self.logger.warning(f"⚠️ Failed to re-subscribe to {len(failed_subscriptions)} topics")
                    else:
                        self.logger.info("✅ All subscriptions restored successfully")
                
                self.logger.info("✅ WebSocket reconnection successful")
                return True
            else:
                self.logger.error("❌ WebSocket reconnection failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Reconnection error: {e}")
            return False
    
    async def _disconnect(self) -> None:
        """연결 해제"""
        self.is_connected = False
        
        # Heartbeat 중지
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        
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

    # =============================================================================
    # Heartbeat 관리
    # =============================================================================
    
    async def _heartbeat_loop(self):
        """STOMP Heartbeat 루프 - 연결 유지"""
        try:
            while self.is_connected and self.websocket and self.is_running:
                await asyncio.sleep(4.0)  # 4초마다 heartbeat
                
                if self.is_connected and self.websocket and self.is_running:
                    await self.websocket.send("\n")  # Heartbeat 전송
                    
        except Exception as e:
            self.logger.warning(f"💓 Heartbeat loop error: {e}")

    # =============================================================================
    # 구독 및 메시지 처리
    # =============================================================================
    
    async def _subscribe(self, topic: str, subscription_id: str = None) -> bool:
        """토픽 구독"""
        if not self.is_connected or not self.websocket:
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
            
            # 응답 대기하지 않음 (메인 리스너에서 처리)
            # 구독 요청 전송 후 바로 성공으로 간주
            self.logger.info(f"✅ Subscribed to: {topic}")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ Subscribe failed: {e}")
            return False
    
    async def _unsubscribe(self, subscription_id: str) -> bool:
        """구독 해제"""
        if not self.is_connected or not self.websocket:
            self.logger.error("❌ Not connected to WebSocket")
            return False
        
        try:
            unsubscribe_headers = {
                "id": subscription_id,
                "receipt": f"{subscription_id}-unsub_receipt"
            }
            
            unsubscribe_frame = self._create_stomp_frame("UNSUBSCRIBE", unsubscribe_headers)
            await self.websocket.send(unsubscribe_frame)
            
            self.logger.info(f"✅ Unsubscribed: {subscription_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Unsubscribe failed: {e}")
            return False
    
    async def _listen_loop(self) -> None:
        """실시간 메시지 수신 루프"""
        try:
            self.logger.info("🎧 Starting real-time message listening...")
            
            while self.is_connected and self.is_running:
                message = await self.websocket.recv()
                parsed_message = self._parse_stomp_frame(message)
                
                # 실제 데이터 메시지만 처리
                if parsed_message['command'] == 'MESSAGE':
                    await self._handle_message(parsed_message)
                
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("🔌 WebSocket connection closed")
            self.is_connected = False
        except asyncio.CancelledError:
            self.logger.info("🛑 Listen loop cancelled")
        except Exception as e:
            self.logger.error(f"❌ Listen error: {e}")
    
    async def _handle_message(self, parsed_message: Dict[str, Any]) -> None:
        """실시간 메시지 처리"""
        try:
            headers = parsed_message.get('headers', {})
            body = parsed_message.get('body', '')
            
            # JSON 파싱 시도
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {"raw_body": body}
            
            # 메시지에 메타데이터 추가
            message_data = {
                "subscription": headers.get('subscription', 'unknown'),
                "content_type": headers.get('content-type', 'unknown'),
                "timestamp": time.time(),
                "data": data
            }
            
            # 로깅
            if data.get('code'):  # 주식 데이터인 경우
                self.logger.info(f"📊 {data.get('code')} | Price: {data.get('close')} | Volume: {data.get('volume')} | Type: {data.get('tradeType')}")
            else:
                self.logger.info(f"📨 Real-time data: {body[:100]}...")
            
            # 등록된 핸들러들에게 메시지 전달
            for handler in self.message_handlers:
                try:
                    # 핸들러가 코루틴인지 확인하고 적절히 호출
                    import asyncio
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message_data)
                    else:
                        handler(message_data)
                except Exception as handler_error:
                    self.logger.error(f"❌ Handler error: {handler_error}")
                    
        except Exception as e:
            self.logger.error(f"❌ Message handling error: {e}")


# =============================================================================
# 글로벌 인스턴스
# =============================================================================

# 싱글톤 WebSocket 서비스 인스턴스
toss_websocket_service = TossWebSocketService()


def get_toss_websocket_service() -> TossWebSocketService:
    """TossWebSocketService 인스턴스 반환"""
    return toss_websocket_service
