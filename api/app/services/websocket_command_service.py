"""
WebSocket 명령 서비스

WebSocket 데몬에 동적으로 구독/구독해제 명령을 전송하는 서비스
"""
import json
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

import redis.asyncio as redis


class WebSocketCommandService:
    """WebSocket 데몬 명령 서비스"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
    
    async def send_subscribe_command(self, topic: str, timeout: int = 30) -> Dict[str, Any]:
        """구독 명령 전송"""
        command_id = str(uuid.uuid4())
        
        command_data = {
            'type': 'subscribe',
            'topic': topic,
            'command_id': command_id,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        try:
            # 명령 전송
            await self.redis_client.publish(
                'websocket_daemon:commands',
                json.dumps(command_data)
            )
            
            self.logger.info(f"📤 Sent subscribe command for: {topic}")
            
            # 결과 대기
            result = await self._wait_for_result(command_id, timeout)
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send subscribe command: {e}")
            return {
                'command_id': command_id,
                'success': False,
                'message': f'Failed to send command: {str(e)}',
                'topic': topic
            }
    
    async def send_unsubscribe_command(self, topic: str, timeout: int = 30) -> Dict[str, Any]:
        """구독해제 명령 전송"""
        command_id = str(uuid.uuid4())
        
        command_data = {
            'type': 'unsubscribe',
            'topic': topic,
            'command_id': command_id,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        try:
            # 명령 전송
            await self.redis_client.publish(
                'websocket_daemon:commands',
                json.dumps(command_data)
            )
            
            self.logger.info(f"📤 Sent unsubscribe command for: {topic}")
            
            # 결과 대기
            result = await self._wait_for_result(command_id, timeout)
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to send unsubscribe command: {e}")
            return {
                'command_id': command_id,
                'success': False,
                'message': f'Failed to send command: {str(e)}',
                'topic': topic
            }
    
    async def get_subscriptions(self, timeout: int = 30) -> Dict[str, Any]:
        """현재 구독 목록 조회"""
        command_id = str(uuid.uuid4())
        
        command_data = {
            'type': 'get_subscriptions',
            'command_id': command_id,
            'timestamp': asyncio.get_event_loop().time()
        }
        
        try:
            # 명령 전송
            await self.redis_client.publish(
                'websocket_daemon:commands',
                json.dumps(command_data)
            )
            
            self.logger.info(f"📤 Sent get subscriptions command")
            
            # 결과 대기
            result = await self._wait_for_result(command_id, timeout)
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get subscriptions: {e}")
            return {
                'command_id': command_id,
                'success': False,
                'message': f'Failed to get subscriptions: {str(e)}',
                'subscriptions': []
            }
    
    async def _wait_for_result(self, command_id: str, timeout: int) -> Dict[str, Any]:
        """명령 결과 대기"""
        result_key = f'websocket_daemon:command_result:{command_id}'
        
        # 폴링으로 결과 대기 (0.5초마다 확인)
        for attempt in range(timeout * 2):  # 0.5초 * timeout * 2
            try:
                result_data = await self.redis_client.get(result_key)
                if result_data:
                    result = json.loads(result_data)
                    self.logger.info(f"📥 Received command result: {command_id}")
                    return result
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"❌ Error waiting for result: {e}")
                break
        
        # 타임아웃
        self.logger.warning(f"⏰ Command timeout: {command_id}")
        return {
            'command_id': command_id,
            'success': False,
            'message': f'Command timeout after {timeout} seconds',
            'timeout': True
        }
    
    async def send_reconnect_command(self) -> Dict[str, Any]:
        """WebSocket 재연결 명령 전송"""
        try:
            command_id = str(uuid.uuid4())
            command_data = {
                'type': 'reconnect',
                'command_id': command_id,
                'timestamp': time.time()
            }
            
            self.logger.info(f"🔄 Sending reconnect command: {command_id}")
            
            # Redis Pub/Sub으로 명령 전송
            await self.redis_client.publish(
                'websocket_daemon:commands',
                json.dumps(command_data)
            )
            
            # 결과 대기 (폴링)
            result = await self._wait_for_result(command_id, timeout=45)  # 재연결은 시간이 더 오래 걸릴 수 있음
            
            if result:
                self.logger.info(f"✅ Reconnect command completed: {result.get('success')}")
                return result
            else:
                self.logger.error("❌ Reconnect command timeout")
                return {
                    'success': False,
                    'message': 'Reconnection command timeout',
                    'command_id': command_id
                }
                
        except Exception as e:
            self.logger.error(f"❌ Send reconnect command failed: {e}")
            raise Exception(f"Failed to send reconnect command: {str(e)}")


async def get_websocket_command_service(redis_client: redis.Redis) -> WebSocketCommandService:
    """WebSocket 명령 서비스 인스턴스 반환"""
    return WebSocketCommandService(redis_client)
