"""
Toss WebSocket STOMP 클라이언트

실시간 주식 데이터 수신을 위한 WebSocket 클라이언트
- 자동 Authorization 토큰 가져오기
- STOMP 프로토콜 지원
- Heartbeat 메커니즘으로 연결 안정화
"""
import asyncio
import websockets
import logging
import requests
import time
import uuid
from typing import Optional, Dict, Any


class TossWebSocketClient:
    """Toss WebSocket STOMP 클라이언트"""
    
    def __init__(self, url: str = "wss://realtime-socket.tossinvest.com/ws"):
        self.url = url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.is_connected = False
        self.device_id = "WTS-6857e1aa2ef34224a9ccfb6f879c1c1e"
        self.connection_id = str(uuid.uuid4())
        self.authorization: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
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
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    # =============================================================================
    # 인증 및 토큰 관리
    # =============================================================================
    
    def fetch_authorization_token(self) -> bool:
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
    
    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """사용자 정의 쿠키 설정"""
        self.cookies.update(cookies)
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
    
    async def connect(self) -> bool:
        """WebSocket 연결 및 STOMP 핸드셰이크"""
        try:
            # 토큰 가져오기
            if not self.authorization:
                self.logger.info("🔄 Authorization token not set, fetching from API...")
                if not self.fetch_authorization_token():
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
    
    async def disconnect(self) -> None:
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
            while self.is_connected and self.websocket:
                await asyncio.sleep(4.0)  # 4초마다 heartbeat
                
                if self.is_connected and self.websocket:
                    await self.websocket.send("\n")  # Heartbeat 전송
                    
        except Exception as e:
            self.logger.warning(f"💓 Heartbeat loop error: {e}")

    # =============================================================================
    # 구독 및 메시지 처리
    # =============================================================================
    
    async def subscribe(self, topic: str, subscription_id: str = None) -> bool:
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
            
            # 구독 응답 대기
            response = await self.websocket.recv()
            parsed_response = self._parse_stomp_frame(response)
            
            if parsed_response.get('headers', {}).get('response-code') == '200':
                self.logger.info(f"✅ Subscribed to: {topic}")
                return True
            else:
                self.logger.warning(f"⚠️ Subscription warning: {parsed_response}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Subscribe failed: {e}")
            return False
    
    async def listen(self) -> None:
        """실시간 메시지 수신"""
        if not self.is_connected or not self.websocket:
            self.logger.error("❌ Not connected to WebSocket")
            return
        
        self.logger.info("🎧 Listening for real-time messages... (Press Ctrl+C to stop)")
        
        try:
            while self.is_connected:
                message = await self.websocket.recv()
                parsed_message = self._parse_stomp_frame(message)
                
                # 실제 데이터 메시지만 처리
                if parsed_message['command'] == 'MESSAGE':
                    self._handle_message(parsed_message)
                
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("🔌 WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            self.logger.error(f"❌ Listen error: {e}")
    
    def _handle_message(self, parsed_message: Dict[str, Any]) -> None:
        """실시간 메시지 처리"""
        headers = parsed_message.get('headers', {})
        body = parsed_message.get('body', '')
        
        # 메시지 정보 출력
        subscription = headers.get('subscription', 'unknown')
        content_type = headers.get('content-type', 'unknown')
        
        self.logger.info("📨 Real-time data received:")
        self.logger.info(f"   Subscription: {subscription}")
        self.logger.info(f"   Content-Type: {content_type}")
        self.logger.info(f"   Data: {body}")
        self.logger.info("-" * 60)


# =============================================================================
# 사용 예시
# =============================================================================

async def real_time_stock():
    """실시간 주식 데이터 수신 예시"""
    try:
        client = TossWebSocketClient()
        
        # 연결
        if await client.connect():
            print("✅ Connected successfully!")
            
            # 삼성전자 실시간 거래 데이터 구독
            await client.subscribe("/topic/v1/kr/stock/trade/A005930")
            # await client.subscribe("/topic/v1/us/stock/trade/US20211220003")
            
            # 실시간 데이터 수신
            await client.listen()
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping client...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(real_time_stock())