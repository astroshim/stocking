"""
Redis 서비스

독립 WebSocket 데몬과 FastAPI 애플리케이션 간 데이터 공유를 위한 Redis 클라이언트
"""
import json
import logging
import os
import time
from typing import Dict, Any, Optional, List
import asyncio

import redis.asyncio as redis


class RedisService:
    """Redis 클라이언트 서비스"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        
        self.logger = logging.getLogger(__name__)
    
    async def connect(self) -> bool:
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
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Redis connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Redis 연결 해제"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("🧹 Redis connection closed")
    
    async def get_realtime_stock_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """실시간 주식 데이터 조회"""
        try:
            if not self.redis_client:
                await self.connect()
            
            redis_key = f"stock:realtime:{stock_code}"
            data = await self.redis_client.get(redis_key)
            
            if data:
                return json.loads(data)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get realtime data for {stock_code}: {e}")
            return None
    
    async def get_multiple_realtime_data(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """여러 종목의 실시간 데이터 조회"""
        try:
            if not self.redis_client:
                await self.connect()
            
            # Redis Pipeline 사용으로 성능 최적화
            pipe = self.redis_client.pipeline()
            
            for stock_code in stock_codes:
                redis_key = f"stock:realtime:{stock_code}"
                pipe.get(redis_key)
            
            results = await pipe.execute()
            
            # 결과 파싱
            stock_data = {}
            for i, (stock_code, data) in enumerate(zip(stock_codes, results)):
                if data:
                    try:
                        stock_data[stock_code] = json.loads(data)
                    except json.JSONDecodeError:
                        self.logger.warning(f"⚠️ Invalid JSON for {stock_code}")
                        stock_data[stock_code] = None
                else:
                    stock_data[stock_code] = None
            
            return stock_data
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get multiple realtime data: {e}")
            return {}
    
    async def get_websocket_daemon_health(self) -> Optional[Dict[str, Any]]:
        """WebSocket 데몬 헬스체크 정보 조회 (실시간 상태 분석 포함)"""
        try:
            if not self.redis_client:
                await self.connect()
            
            health_data = await self.redis_client.get('websocket_daemon:health')
            
            if health_data:
                parsed_data = json.loads(health_data)
                
                # 실시간 상태 분석 추가
                current_time = time.time()
                last_updated = parsed_data.get('last_updated', 0)
                time_since_update = current_time - last_updated
                
                # 실제 프로세스 상태 판단 (업데이트 주기가 20초로 변경됨에 따라 조정)
                is_stale = time_since_update > 45  # 45초 이상 업데이트 없으면 stale (20초 × 2 + 여유분)
                is_likely_dead = time_since_update > 90  # 90초 이상 업데이트 없으면 dead로 간주 (20초 × 4 + 여유분)
                
                # 추가 정보 포함
                parsed_data['analysis'] = {
                    'current_time': current_time,
                    'time_since_last_update': time_since_update,
                    'time_since_last_update_formatted': self._format_time_ago(time_since_update),
                    'is_stale': is_stale,
                    'is_likely_dead': is_likely_dead,
                    'status': self._determine_daemon_status(is_stale, is_likely_dead, parsed_data)
                }
                
                return parsed_data
            else:
                return {
                    'analysis': {
                        'current_time': time.time(),
                        'is_stale': True,
                        'is_likely_dead': True,
                        'status': 'NO_DATA',
                        'message': 'Redis에서 헬스 데이터를 찾을 수 없습니다.'
                    }
                }
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get daemon health: {e}")
            return None
    
    def _format_time_ago(self, seconds_ago: float) -> str:
        """시간을 '몇 초 전' 형태로 포맷"""
        try:
            seconds = int(seconds_ago)
            
            if seconds < 60:
                return f"{seconds}초 전"
            elif seconds < 3600:
                minutes = seconds // 60
                return f"{minutes}분 전"
            elif seconds < 86400:
                hours = seconds // 3600
                return f"{hours}시간 전"
            else:
                days = seconds // 86400
                return f"{days}일 전"
                
        except Exception:
            return f"{seconds_ago:.1f}초 전"
    
    def _determine_daemon_status(self, is_stale: bool, is_likely_dead: bool, health_data: dict) -> str:
        """데몬 상태 판단"""
        try:
            if is_likely_dead:
                return 'DEAD'
            elif is_stale:
                return 'STALE'
            elif not health_data.get('websocket_connected', False):
                return 'WEBSOCKET_DISCONNECTED'
            elif not health_data.get('websocket_running', False):
                return 'WEBSOCKET_STOPPED'
            elif not health_data.get('redis_connected', False):
                return 'REDIS_DISCONNECTED'
            else:
                return 'HEALTHY'
                
        except Exception:
            return 'UNKNOWN'
    
    async def subscribe_to_stock_updates(self, stock_code: str, callback):
        """주식 업데이트 구독 (Pub/Sub)"""
        try:
            if not self.redis_client:
                await self.connect()
            
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(f"stock_updates:{stock_code}")
            
            self.logger.info(f"📡 Subscribed to stock updates: {stock_code}")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        await callback(stock_code, data)
                    except Exception as e:
                        self.logger.error(f"❌ Callback error: {e}")
                        
        except Exception as e:
            self.logger.error(f"❌ Subscribe error for {stock_code}: {e}")
    
    async def get_all_realtime_stocks(self) -> List[str]:
        """현재 실시간 데이터가 있는 모든 종목 코드 조회"""
        try:
            if not self.redis_client:
                await self.connect()
            
            pattern = "stock:realtime:*"
            keys = await self.redis_client.keys(pattern)
            
            # 키에서 종목 코드 추출
            stock_codes = []
            for key in keys:
                if key.startswith("stock:realtime:"):
                    stock_code = key.replace("stock:realtime:", "")
                    stock_codes.append(stock_code)
            
            return stock_codes
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get all realtime stocks: {e}")
            return []


# 싱글톤 인스턴스
_redis_service_instance = None


async def get_redis_service() -> RedisService:
    """Redis 서비스 인스턴스 반환 (싱글톤)"""
    global _redis_service_instance
    
    if _redis_service_instance is None:
        _redis_service_instance = RedisService()
        # 초기 연결 시도
        await _redis_service_instance.connect()
    
    return _redis_service_instance
