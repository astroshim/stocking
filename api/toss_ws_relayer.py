#!/usr/bin/env python3
"""
독립 WebSocket 릴레이어 프로세스

Gunicorn worker와 별개로 실행되는 WebSocket 서비스
실시간 데이터를 Redis를 통해 FastAPI 애플리케이션과 공유
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time
from typing import Dict, Any

import redis.asyncio as redis

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.toss_websocket_service import TossWebSocketService


class TossWsRelayer:
    """독립 WebSocket 릴레이어"""
    
    def __init__(self):
        self.running = False
        self.websocket_service = TossWebSocketService()
        self.redis_client: redis.Redis = None
        self.start_time = time.time()  # 릴레이어 시작 시간
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/tmp/toss_ws_relayer.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Redis 설정
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        self.logger.info(f"🛑 Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self):
        """릴레이어 시작"""
        try:
            self.logger.info("🚀 Starting Toss WebSocket Relayer...")
            self.running = True
            
            # Redis 연결
            await self._connect_redis()
            
            # WebSocket 서비스 설정
            self._setup_websocket_service()
            
            # WebSocket 서비스 시작
            if await self.websocket_service.start():
                self.logger.info("✅ Toss WebSocket Relayer started successfully")
                
                # 명령 채널 리스너 시작
                command_task = asyncio.create_task(self._listen_for_commands())
                
                # 메인 루프와 명령 리스너 동시 실행
                await asyncio.gather(
                    self._main_loop(),
                    command_task,
                    return_exceptions=True
                )
            else:
                self.logger.error("❌ Failed to start WebSocket service")
                
        except Exception as e:
            self.logger.error(f"❌ Relayer startup error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """릴레이어 중지"""
        try:
            self.logger.info("🛑 Stopping Toss WebSocket Relayer...")
            self.running = False
            
            # WebSocket 서비스 중지
            if self.websocket_service:
                await self.websocket_service.stop()
            
            # Redis 연결 해제
            if self.redis_client:
                await self.redis_client.close()
            
            self.logger.info("✅ Toss WebSocket Relayer stopped")
            
        except Exception as e:
            self.logger.error(f"❌ Relayer shutdown error: {e}")
    
    async def _connect_redis(self):
        """Redis 연결"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # 연결 테스트
            await self.redis_client.ping()
            self.logger.info(f"✅ Connected to Redis: {self.redis_host}:{self.redis_port}")
            
        except Exception as e:
            self.logger.error(f"❌ Redis connection failed: {e}")
            raise
    
    def _setup_websocket_service(self):
        """WebSocket 서비스 설정"""
        # # 기본 구독 추가
        # self.websocket_service.add_subscription("/topic/v1/kr/stock/trade/A005930")  # 삼성전자
        # self.websocket_service.add_subscription("/topic/v1/kr/stock/trade/A000660")  # SK하이닉스
        
        # 메시지 핸들러 추가
        self.websocket_service.add_message_handler(self._handle_stock_message)
    
    async def _handle_stock_message(self, message_data: Dict[str, Any]):
        """주식 메시지 처리 및 Redis 저장"""
        try:
            data = message_data.get('data', {})
            stock_code = data.get('code')
            
            if stock_code:
                # Redis에 실시간 데이터 저장
                redis_key = f"stock:realtime:{stock_code}"
                
                # 메시지에 타임스탬프 추가
                enriched_data = {
                    **message_data,
                    'daemon_timestamp': time.time(),
                    'daemon_pid': os.getpid()
                }
                
                # Redis에 저장 (TTL 1시간)
                await self.redis_client.setex(
                    redis_key,
                    3600,  # 1시간 TTL
                    json.dumps(enriched_data)
                )
                
                # Pub/Sub으로 실시간 알림
                await self.redis_client.publish(
                    f"stock_updates:{stock_code}",
                    json.dumps(enriched_data)
                )
                
                # 로깅
                price = data.get('close', 'N/A')
                volume = data.get('volume', 'N/A')
                trade_type = data.get('tradeType', 'N/A')
                
                self.logger.info(
                    f"📊 {stock_code} | Price: {price} | Volume: {volume} | Type: {trade_type}"
                )
                
        except Exception as e:
            self.logger.error(f"❌ Message handling error: {e}")
    
    async def _main_loop(self):
        """메인 실행 루프"""
        try:
            self.logger.info("🔄 Starting main loop...")
            
            while self.running:
                # 헬스체크 정보 업데이트
                await self._update_health_status()
                
                # 20초마다 상태 업데이트 (더 빠른 주기로 안정성 향상)
                await asyncio.sleep(20)
                
        except asyncio.CancelledError:
            self.logger.info("🛑 Main loop cancelled")
        except Exception as e:
            self.logger.error(f"❌ Main loop error: {e}")
    
    async def _listen_for_commands(self):
        """Redis 명령 채널 리스닝"""
        try:
            self.logger.info("🎧 Starting command listener...")
            
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe('toss_ws_relayer:commands')
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        command_data = json.loads(message['data'])
                        await self._process_command(command_data)
                    except Exception as e:
                        self.logger.error(f"❌ Command processing error: {e}")
                        
        except Exception as e:
            self.logger.error(f"❌ Command listener error: {e}")
    
    async def _process_command(self, command_data: Dict[str, Any]):
        """명령 처리"""
        try:
            command_type = command_data.get('type')
            topic = command_data.get('topic')
            command_id = command_data.get('command_id', 'unknown')
            
            self.logger.info(f"📩 Processing command: {command_type} for topic: {topic}")
            
            if command_type == 'subscribe':
                await self._handle_subscribe_command(topic, command_id)
            elif command_type == 'unsubscribe':
                await self._handle_unsubscribe_command(topic, command_id)
            elif command_type == 'get_subscriptions':
                await self._handle_get_subscriptions_command(command_id)
            elif command_type == 'reconnect':
                await self._handle_reconnect_command(command_data)
            else:
                self.logger.warning(f"⚠️ Unknown command type: {command_type}")
                
        except Exception as e:
            self.logger.error(f"❌ Command processing failed: {e}")
    
    async def _handle_subscribe_command(self, topic: str, command_id: str):
        """구독 명령 처리"""
        try:
            if topic in self.websocket_service.subscriptions:
                # 이미 구독 중인 경우
                result = {
                    'command_id': command_id,
                    'success': True,
                    'message': f'Already subscribed to {topic}',
                    'topic': topic
                }
            else:
                # 새로운 구독
                self.websocket_service.add_subscription(topic)
                
                # WebSocket이 연결되어 있으면 즉시 구독
                if self.websocket_service.is_connected:
                    success = await self.websocket_service._subscribe(topic)
                    if success:
                        result = {
                            'command_id': command_id,
                            'success': True,
                            'message': f'Successfully subscribed to {topic}',
                            'topic': topic
                        }
                    else:
                        result = {
                            'command_id': command_id,
                            'success': False,
                            'message': f'Failed to subscribe to {topic}',
                            'topic': topic
                        }
                else:
                    result = {
                        'command_id': command_id,
                        'success': True,
                        'message': f'Added {topic} to subscription list (will subscribe when connected)',
                        'topic': topic
                    }
            
            # 결과를 Redis에 저장
            await self.redis_client.setex(
                f'toss_ws_relayer:command_result:{command_id}',
                60,  # 1분 TTL
                json.dumps(result)
            )
            
            self.logger.info(f"✅ Subscribe command processed: {topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Subscribe command failed: {e}")
    
    async def _handle_unsubscribe_command(self, topic: str, command_id: str):
        """구독해제 명령 처리"""
        try:
            if topic not in self.websocket_service.subscriptions:
                # 구독하지 않은 토픽인 경우
                result = {
                    'command_id': command_id,
                    'success': True,
                    'message': f'Not subscribed to {topic}',
                    'topic': topic
                }
            else:
                # 구독해제
                self.websocket_service.remove_subscription(topic)
                
                # WebSocket이 연결되어 있으면 즉시 구독해제
                if self.websocket_service.is_connected:
                    # TossWebSocketService에 unsubscribe 메소드가 있다면 호출
                    try:
                        subscription_id = str(abs(hash(topic)) % 10000)
                        if hasattr(self.websocket_service, '_unsubscribe'):
                            success = await self.websocket_service._unsubscribe(subscription_id)
                        else:
                            success = True  # 목록에서만 제거
                        
                        result = {
                            'command_id': command_id,
                            'success': success,
                            'message': f'Successfully unsubscribed from {topic}' if success else f'Failed to unsubscribe from {topic}',
                            'topic': topic
                        }
                    except Exception as unsub_error:
                        self.logger.warning(f"⚠️ Unsubscribe websocket error: {unsub_error}")
                        result = {
                            'command_id': command_id,
                            'success': True,
                            'message': f'Removed {topic} from subscription list',
                            'topic': topic
                        }
                else:
                    result = {
                        'command_id': command_id,
                        'success': True,
                        'message': f'Removed {topic} from subscription list',
                        'topic': topic
                    }
            
            # 결과를 Redis에 저장
            await self.redis_client.setex(
                f'toss_ws_relayer:command_result:{command_id}',
                60,  # 1분 TTL
                json.dumps(result)
            )
            
            self.logger.info(f"✅ Unsubscribe command processed: {topic}")
            
        except Exception as e:
            self.logger.error(f"❌ Unsubscribe command failed: {e}")
    
    async def _handle_get_subscriptions_command(self, command_id: str):
        """구독 목록 조회 명령 처리"""
        try:
            result = {
                'command_id': command_id,
                'success': True,
                'subscriptions': self.websocket_service.subscriptions,
                'total_count': len(self.websocket_service.subscriptions),
                'websocket_connected': self.websocket_service.is_connected
            }
            
            # 결과를 Redis에 저장
            await self.redis_client.setex(
                f'toss_ws_relayer:command_result:{command_id}',
                60,  # 1분 TTL
                json.dumps(result)
            )
            
            self.logger.info(f"✅ Get subscriptions command processed")
            
        except Exception as e:
            self.logger.error(f"❌ Get subscriptions command failed: {e}")
    
    async def _handle_reconnect_command(self, command_data: dict):
        """재연결 명령 처리"""
        try:
            command_id = command_data.get('command_id')
            self.logger.info(f"🔄 Processing reconnect command: {command_id}")
            
            # WebSocket 재연결 시도
            success = await self.websocket_service.reconnect()
            
            if success:
                result_data = {
                    'command_id': command_id,
                    'success': True,
                    'message': 'WebSocket reconnection successful',
                    'connection_status': {
                        'websocket_connected': self.websocket_service.is_connected,
                        'websocket_running': self.websocket_service.is_running,
                        'subscription_count': len(self.websocket_service.subscriptions)
                    }
                }
                self.logger.info("✅ WebSocket reconnection successful")
            else:
                result_data = {
                    'command_id': command_id,
                    'success': False,
                    'message': 'WebSocket reconnection failed',
                    'connection_status': {
                        'websocket_connected': self.websocket_service.is_connected,
                        'websocket_running': self.websocket_service.is_running,
                        'subscription_count': len(self.websocket_service.subscriptions)
                    }
                }
                self.logger.error("❌ WebSocket reconnection failed")
            
            # 결과를 Redis에 저장
            await self.redis_client.setex(
                f'toss_ws_relayer:command_result:{command_id}',
                60,  # 1분 TTL
                json.dumps(result_data)
            )
            
            self.logger.info(f"✅ Reconnect command processed: {command_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Reconnect command failed: {e}")
            
            # 실패 결과 저장
            if 'command_id' in locals():
                try:
                    error_result = {
                        'command_id': command_id,
                        'success': False,
                        'message': f'Reconnection error: {str(e)}',
                        'connection_status': {
                            'websocket_connected': False,
                            'websocket_running': False,
                            'subscription_count': 0
                        }
                    }
                    await self.redis_client.setex(
                        f'toss_ws_relayer:command_result:{command_id}',
                        60,
                        json.dumps(error_result)
                    )
                except Exception as redis_e:
                    self.logger.error(f"❌ Failed to save error result: {redis_e}")

    async def _update_health_status(self):
        """헬스체크 상태 업데이트"""
        try:
            current_time = time.time()
            uptime_seconds = current_time - self.start_time
            
            health_data = {
                'daemon_pid': os.getpid(),
                'start_time': self.start_time,
                'last_updated': current_time,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': self._format_uptime(uptime_seconds),
                'websocket_connected': self.websocket_service.is_connected,
                'websocket_running': self.websocket_service.is_running,
                'subscriptions': self.websocket_service.subscriptions,
                'subscription_count': len(self.websocket_service.subscriptions),
                'redis_connected': self.redis_client is not None
            }
            
            await self.redis_client.setex(
                'toss_ws_relayer:health',
                300,  # 5분 TTL (30초 × 10회 여유)
                json.dumps(health_data)
            )
            
            self.logger.debug(f"✅ Health status updated successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Health status update failed: {e}")
            # 재시도 로직
            try:
                self.logger.info("🔄 Retrying health status update...")
                await asyncio.sleep(2)  # 2초 대기 후 재시도
                await self.redis_client.setex(
                    'toss_ws_relayer:health',
                    300,  # 5분 TTL
                    json.dumps(health_data)
                )
                self.logger.info("✅ Health status update retry successful")
            except Exception as retry_e:
                self.logger.error(f"💥 Health status update retry failed: {retry_e}")
                # Redis 연결 재시도
                try:
                    await self._connect_redis()
                    self.logger.info("🔗 Redis reconnection successful")
                except Exception as conn_e:
                    self.logger.error(f"🔌 Redis reconnection failed: {conn_e}")
    
    def _format_uptime(self, uptime_seconds: float) -> str:
        """업타임을 읽기 쉬운 형태로 포맷"""
        try:
            seconds = int(uptime_seconds)
            
            if seconds < 60:
                return f"{seconds}초"
            elif seconds < 3600:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                return f"{minutes}분 {remaining_seconds}초"
            elif seconds < 86400:
                hours = seconds // 3600
                remaining_minutes = (seconds % 3600) // 60
                return f"{hours}시간 {remaining_minutes}분"
            else:
                days = seconds // 86400
                remaining_hours = (seconds % 86400) // 3600
                return f"{days}일 {remaining_hours}시간"
                
        except Exception:
            return f"{uptime_seconds:.1f}초"


async def main():
    """메인 함수"""
    relayer = TossWsRelayer()
    
    try:
        await relayer.start()
    except KeyboardInterrupt:
        relayer.logger.info("🛑 Received KeyboardInterrupt")
    except Exception as e:
        relayer.logger.error(f"❌ Relayer error: {e}")
    finally:
        await relayer.stop()


if __name__ == "__main__":
    print("🚀 Starting Toss WebSocket Relayer Process...")
    asyncio.run(main())
