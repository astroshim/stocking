"""
Subscription Manager for dynamic topic management
동적 구독 관리 시스템
"""
import asyncio
import logging
import json
from typing import Dict, Set, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .models import SubscriptionRequest, MessageType, ProxyMessage


class SubscriptionStatus(str, Enum):
    """구독 상태"""
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"


@dataclass
class SubscriptionInfo:
    """구독 정보"""
    topic: str
    subscription_id: str
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    activated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    auto_managed: bool = True  # 자동 관리 여부
    metadata: Dict = field(default_factory=dict)


class SubscriptionManager:
    """구독 관리자"""
    
    def __init__(self, websocket_client=None):
        self.websocket_client = websocket_client
        self.subscriptions: Dict[str, SubscriptionInfo] = {}  # subscription_id -> SubscriptionInfo
        self.topic_to_subscription: Dict[str, str] = {}  # topic -> subscription_id
        
        # 구독 요청 큐
        self.subscription_queue: asyncio.Queue = asyncio.Queue()
        self.unsubscription_queue: asyncio.Queue = asyncio.Queue()
        
        # 관리 태스크
        self.manager_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 콜백 함수들
        self.on_subscription_success: Optional[Callable] = None
        self.on_subscription_failure: Optional[Callable] = None
        self.on_message_received: Optional[Callable] = None
        
        # 로깅
        self.logger = logging.getLogger("SubscriptionManager")
    
    def set_websocket_client(self, client) -> None:
        """WebSocket 클라이언트 설정"""
        self.websocket_client = client
    
    def start(self) -> None:
        """구독 관리자 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self.manager_task = asyncio.create_task(self._manager_loop())
        self.logger.info("🎯 SubscriptionManager started")
    
    async def stop(self) -> None:
        """구독 관리자 중지"""
        self.is_running = False
        
        if self.manager_task and not self.manager_task.done():
            self.manager_task.cancel()
            try:
                await self.manager_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🎯 SubscriptionManager stopped")
    
    # =============================================================================
    # 구독 요청 API
    # =============================================================================
    
    async def request_subscription(self, topic: str, subscription_id: Optional[str] = None, 
                                 auto_managed: bool = True, metadata: Dict = None) -> str:
        """구독 요청 (비동기)"""
        if subscription_id is None:
            subscription_id = self._generate_subscription_id(topic)
        
        # 이미 구독된 토픽인지 확인
        if topic in self.topic_to_subscription:
            existing_id = self.topic_to_subscription[topic]
            existing_sub = self.subscriptions.get(existing_id)
            if existing_sub and existing_sub.status == SubscriptionStatus.ACTIVE:
                self.logger.warning(f"Topic {topic} already subscribed with ID {existing_id}")
                return existing_id
        
        # 구독 정보 생성
        subscription_info = SubscriptionInfo(
            topic=topic,
            subscription_id=subscription_id,
            auto_managed=auto_managed,
            metadata=metadata or {}
        )
        
        self.subscriptions[subscription_id] = subscription_info
        self.topic_to_subscription[topic] = subscription_id
        
        # 구독 요청 큐에 추가
        request = SubscriptionRequest(
            topic=topic,
            subscription_id=subscription_id,
            auto_generate_id=False
        )
        
        await self.subscription_queue.put(request)
        self.logger.info(f"📝 Subscription requested: {topic} (ID: {subscription_id})")
        
        return subscription_id
    
    async def request_unsubscription(self, topic: Optional[str] = None, 
                                   subscription_id: Optional[str] = None) -> bool:
        """구독 해제 요청"""
        if subscription_id is None and topic is not None:
            subscription_id = self.topic_to_subscription.get(topic)
        
        if subscription_id is None:
            self.logger.error(f"Cannot find subscription for topic: {topic}")
            return False
        
        if subscription_id not in self.subscriptions:
            self.logger.error(f"Subscription not found: {subscription_id}")
            return False
        
        await self.unsubscription_queue.put(subscription_id)
        self.logger.info(f"📝 Unsubscription requested: {subscription_id}")
        
        return True
    
    def _generate_subscription_id(self, topic: str) -> str:
        """구독 ID 생성"""
        # 토픽 기반 해시 + 타임스탬프
        import hashlib
        import time
        
        hash_part = hashlib.md5(topic.encode()).hexdigest()[:8]
        timestamp_part = str(int(time.time() * 1000))[-6:]
        
        return f"sub_{hash_part}_{timestamp_part}"
    
    # =============================================================================
    # 관리 루프
    # =============================================================================
    
    async def _manager_loop(self) -> None:
        """구독 관리 메인 루프"""
        self.logger.info("🎯 Subscription manager loop started")
        
        while self.is_running:
            try:
                # 구독 요청 처리
                await self._process_subscription_requests()
                
                # 구독 해제 요청 처리
                await self._process_unsubscription_requests()
                
                # 구독 상태 모니터링
                await self._monitor_subscriptions()
                
                # 잠시 대기
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"❌ Manager loop error: {e}")
                await asyncio.sleep(1.0)
        
        self.logger.info("🎯 Subscription manager loop ended")
    
    async def _process_subscription_requests(self) -> None:
        """구독 요청 처리"""
        try:
            while not self.subscription_queue.empty():
                request = await asyncio.wait_for(self.subscription_queue.get(), timeout=0.1)
                await self._handle_subscription_request(request)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.logger.error(f"❌ Subscription request processing error: {e}")
    
    async def _process_unsubscription_requests(self) -> None:
        """구독 해제 요청 처리"""
        try:
            while not self.unsubscription_queue.empty():
                subscription_id = await asyncio.wait_for(self.unsubscription_queue.get(), timeout=0.1)
                await self._handle_unsubscription_request(subscription_id)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.logger.error(f"❌ Unsubscription request processing error: {e}")
    
    async def _handle_subscription_request(self, request: SubscriptionRequest) -> None:
        """개별 구독 요청 처리"""
        subscription_id = request.subscription_id
        topic = request.topic
        
        if not self.websocket_client:
            self.logger.error("WebSocket client not available")
            self._mark_subscription_failed(subscription_id, "WebSocket client not available")
            return
        
        try:
            # WebSocket 클라이언트를 통해 구독
            success = await self.websocket_client.subscribe(topic, subscription_id)
            
            if success:
                self._mark_subscription_active(subscription_id)
                if self.on_subscription_success:
                    await self._safe_callback(self.on_subscription_success, subscription_id, topic)
            else:
                self._mark_subscription_failed(subscription_id, "WebSocket subscription failed")
                if self.on_subscription_failure:
                    await self._safe_callback(self.on_subscription_failure, subscription_id, topic, "WebSocket subscription failed")
                    
        except Exception as e:
            self.logger.error(f"❌ Subscription error for {topic}: {e}")
            self._mark_subscription_failed(subscription_id, str(e))
            if self.on_subscription_failure:
                await self._safe_callback(self.on_subscription_failure, subscription_id, topic, str(e))
    
    async def _handle_unsubscription_request(self, subscription_id: str) -> None:
        """개별 구독 해제 요청 처리"""
        if subscription_id not in self.subscriptions:
            self.logger.error(f"Subscription not found for unsubscription: {subscription_id}")
            return
        
        subscription_info = self.subscriptions[subscription_id]
        
        try:
            if self.websocket_client:
                await self.websocket_client.unsubscribe(subscription_id)
            
            # 구독 정보 제거
            self.subscriptions.pop(subscription_id, None)
            self.topic_to_subscription.pop(subscription_info.topic, None)
            
            self.logger.info(f"✅ Unsubscribed: {subscription_info.topic} (ID: {subscription_id})")
            
        except Exception as e:
            self.logger.error(f"❌ Unsubscription error for {subscription_id}: {e}")
    
    def _mark_subscription_active(self, subscription_id: str) -> None:
        """구독을 활성 상태로 표시"""
        if subscription_id in self.subscriptions:
            subscription_info = self.subscriptions[subscription_id]
            subscription_info.status = SubscriptionStatus.ACTIVE
            subscription_info.activated_at = datetime.now()
            self.logger.info(f"✅ Subscription activated: {subscription_info.topic} (ID: {subscription_id})")
    
    def _mark_subscription_failed(self, subscription_id: str, error_message: str) -> None:
        """구독을 실패 상태로 표시"""
        if subscription_id in self.subscriptions:
            subscription_info = self.subscriptions[subscription_id]
            subscription_info.status = SubscriptionStatus.FAILED
            subscription_info.error_count += 1
            subscription_info.metadata['last_error'] = error_message
            self.logger.error(f"❌ Subscription failed: {subscription_info.topic} (ID: {subscription_id}) - {error_message}")
    
    async def _monitor_subscriptions(self) -> None:
        """구독 상태 모니터링"""
        current_time = datetime.now()
        
        for subscription_id, subscription_info in list(self.subscriptions.items()):
            # 오래된 pending 구독 체크 (30초)
            if (subscription_info.status == SubscriptionStatus.PENDING and 
                (current_time - subscription_info.created_at).total_seconds() > 30):
                
                self.logger.warning(f"⏰ Subscription timeout: {subscription_info.topic} (ID: {subscription_id})")
                self._mark_subscription_failed(subscription_id, "Subscription timeout")
            
            # 비활성 구독 체크 (5분간 메시지 없음)
            if (subscription_info.status == SubscriptionStatus.ACTIVE and 
                subscription_info.last_message_at and
                (current_time - subscription_info.last_message_at).total_seconds() > 300):
                
                self.logger.warning(f"📵 No messages for 5 minutes: {subscription_info.topic} (ID: {subscription_id})")
    
    async def _safe_callback(self, callback: Callable, *args, **kwargs) -> None:
        """안전한 콜백 실행"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"❌ Callback error: {e}")
    
    # =============================================================================
    # 메시지 처리
    # =============================================================================
    
    async def handle_message(self, message: ProxyMessage) -> None:
        """메시지 수신 처리 (WebSocket 클라이언트에서 호출)"""
        subscription_id = message.subscription_id
        
        if subscription_id and subscription_id in self.subscriptions:
            subscription_info = self.subscriptions[subscription_id]
            subscription_info.last_message_at = datetime.now()
            subscription_info.message_count += 1
            
            # 메시지 수신 콜백 호출
            if self.on_message_received:
                await self._safe_callback(self.on_message_received, subscription_id, message)
    
    # =============================================================================
    # 상태 조회 API
    # =============================================================================
    
    def get_subscription_info(self, subscription_id: str) -> Optional[SubscriptionInfo]:
        """구독 정보 조회"""
        return self.subscriptions.get(subscription_id)
    
    def get_subscription_by_topic(self, topic: str) -> Optional[SubscriptionInfo]:
        """토픽으로 구독 정보 조회"""
        subscription_id = self.topic_to_subscription.get(topic)
        if subscription_id:
            return self.subscriptions.get(subscription_id)
        return None
    
    def get_active_subscriptions(self) -> List[SubscriptionInfo]:
        """활성 구독 목록 조회"""
        return [
            sub for sub in self.subscriptions.values()
            if sub.status == SubscriptionStatus.ACTIVE
        ]
    
    def get_all_subscriptions(self) -> List[SubscriptionInfo]:
        """전체 구독 목록 조회"""
        return list(self.subscriptions.values())
    
    def get_subscription_stats(self) -> Dict:
        """구독 통계 정보"""
        total_count = len(self.subscriptions)
        active_count = len([s for s in self.subscriptions.values() if s.status == SubscriptionStatus.ACTIVE])
        failed_count = len([s for s in self.subscriptions.values() if s.status == SubscriptionStatus.FAILED])
        pending_count = len([s for s in self.subscriptions.values() if s.status == SubscriptionStatus.PENDING])
        
        total_messages = sum(s.message_count for s in self.subscriptions.values())
        total_errors = sum(s.error_count for s in self.subscriptions.values())
        
        return {
            "total_subscriptions": total_count,
            "active_subscriptions": active_count,
            "failed_subscriptions": failed_count,
            "pending_subscriptions": pending_count,
            "total_messages_received": total_messages,
            "total_errors": total_errors,
            "queue_sizes": {
                "subscription_queue": self.subscription_queue.qsize(),
                "unsubscription_queue": self.unsubscription_queue.qsize()
            }
        }
    
    # =============================================================================
    # 편의 메서드
    # =============================================================================
    
    async def subscribe_to_stock(self, symbol: str, market: str = "kr") -> str:
        """주식 심볼로 간편 구독"""
        if market == "kr":
            topic = f"/topic/v1/kr/stock/trade/{symbol}"
        elif market == "us":
            topic = f"/topic/v1/us/stock/trade/{symbol}"
        else:
            raise ValueError(f"Unsupported market: {market}")
        
        return await self.request_subscription(
            topic=topic,
            metadata={"symbol": symbol, "market": market, "type": "stock_trade"}
        )
    
    async def unsubscribe_from_stock(self, symbol: str, market: str = "kr") -> bool:
        """주식 심볼로 간편 구독 해제"""
        if market == "kr":
            topic = f"/topic/v1/kr/stock/trade/{symbol}"
        elif market == "us":
            topic = f"/topic/v1/us/stock/trade/{symbol}"
        else:
            raise ValueError(f"Unsupported market: {market}")
        
        return await self.request_unsubscription(topic=topic)
    
    async def bulk_subscribe_stocks(self, symbols: List[str], market: str = "kr") -> List[str]:
        """여러 주식 심볼 일괄 구독"""
        subscription_ids = []
        
        for symbol in symbols:
            try:
                subscription_id = await self.subscribe_to_stock(symbol, market)
                subscription_ids.append(subscription_id)
            except Exception as e:
                self.logger.error(f"❌ Failed to subscribe to {symbol}: {e}")
        
        return subscription_ids
    
    async def clear_all_subscriptions(self) -> None:
        """모든 구독 해제"""
        subscription_ids = list(self.subscriptions.keys())
        
        for subscription_id in subscription_ids:
            await self.request_unsubscription(subscription_id=subscription_id)
        
        self.logger.info(f"🧹 Requested unsubscription for all {len(subscription_ids)} subscriptions")
