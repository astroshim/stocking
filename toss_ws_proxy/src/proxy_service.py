"""
Main Toss WebSocket Proxy Service
메인 프록시 서비스 - 모든 컴포넌트 통합
"""
import asyncio
import logging
import signal
import sys
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .config import config
from .toss_client import TossWebSocketProxy
from .worker_handler import WorkerPool, AsyncMessageBridge, custom_stock_processor
from .subscription_manager import SubscriptionManager
from .health_monitor import HealthMonitor, HealthStatus
from .models import ProxyMessage, MessageType, ConnectionStatus


class TossProxyService:
    """Toss WebSocket 프록시 메인 서비스"""
    
    def __init__(self, message_processor: Optional[Callable] = None):
        # 컴포넌트 초기화
        self.websocket_client: Optional[TossWebSocketProxy] = None
        self.worker_pool: Optional[WorkerPool] = None
        self.message_bridge: Optional[AsyncMessageBridge] = None
        self.subscription_manager: Optional[SubscriptionManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        
        # 서비스 상태
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # 메시지 처리기
        self.message_processor = message_processor or custom_stock_processor
        
        # 통계
        self.start_time: Optional[datetime] = None
        self.total_messages_received = 0
        self.total_messages_processed = 0
        
        # 로깅 설정
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format=config.log_format
        )
        self.logger = logging.getLogger("TossProxyService")
        
        # 시그널 핸들러 설정
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """시그널 핸들러 설정"""
        def signal_handler(signum, frame):
            self.logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    # =============================================================================
    # 서비스 생명주기
    # =============================================================================
    
    async def start(self) -> bool:
        """프록시 서비스 시작"""
        if self.is_running:
            self.logger.warning("Service already running")
            return True
        
        self.logger.info("🚀 Starting Toss WebSocket Proxy Service...")
        self.start_time = datetime.now()
        
        try:
            # 1. 워커 풀 초기화 및 시작
            self.logger.info("📦 Initializing worker pool...")
            self.worker_pool = WorkerPool(self.message_processor)
            self.worker_pool.start()
            
            # 2. 메시지 브리지 초기화
            self.logger.info("🌉 Initializing message bridge...")
            self.message_bridge = AsyncMessageBridge(self.worker_pool)
            self.message_bridge.start()
            
            # 3. WebSocket 클라이언트 초기화
            self.logger.info("📡 Initializing WebSocket client...")
            self.websocket_client = TossWebSocketProxy(
                message_handler=self._handle_websocket_message
            )
            
            # 4. 구독 관리자 초기화
            self.logger.info("🎯 Initializing subscription manager...")
            self.subscription_manager = SubscriptionManager(self.websocket_client)
            self.subscription_manager.set_websocket_client(self.websocket_client)
            self.subscription_manager.on_subscription_success = self._on_subscription_success
            self.subscription_manager.on_subscription_failure = self._on_subscription_failure
            self.subscription_manager.on_message_received = self._on_message_received
            self.subscription_manager.start()
            
            # 5. 헬스 모니터 초기화
            self.logger.info("🏥 Initializing health monitor...")
            self.health_monitor = HealthMonitor(
                websocket_client=self.websocket_client,
                subscription_manager=self.subscription_manager,
                worker_pool=self.worker_pool
            )
            self.health_monitor.on_health_status_change = self._on_health_status_change
            self.health_monitor.on_critical_error = self._on_critical_error
            self.health_monitor.on_recovery_needed = self._on_recovery_needed
            self.health_monitor.start()
            
            # 6. WebSocket 연결 시도
            self.logger.info("🔌 Connecting to Toss WebSocket...")
            if not await self.websocket_client.connect():
                self.logger.error("❌ Failed to connect to WebSocket")
                await self.stop()
                return False
            
            self.is_running = True
            self.logger.info("✅ Toss WebSocket Proxy Service started successfully!")
            
            # 기본 구독 추가 (예시)
            await self._setup_default_subscriptions()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Service startup failed: {e}")
            await self.stop()
            return False
    
    async def stop(self) -> None:
        """프록시 서비스 중지"""
        if not self.is_running:
            return
        
        self.logger.info("🛑 Stopping Toss WebSocket Proxy Service...")
        self.is_running = False
        self.shutdown_event.set()
        
        try:
            # 1. 헬스 모니터 중지
            if self.health_monitor:
                await self.health_monitor.stop()
            
            # 2. 구독 관리자 중지
            if self.subscription_manager:
                await self.subscription_manager.stop()
            
            # 3. WebSocket 연결 해제
            if self.websocket_client:
                await self.websocket_client.disconnect()
            
            # 4. 메시지 브리지 중지
            if self.message_bridge:
                await self.message_bridge.stop()
            
            # 5. 워커 풀 중지
            if self.worker_pool:
                self.worker_pool.stop()
            
            self.logger.info("✅ Toss WebSocket Proxy Service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Service shutdown error: {e}")
    
    async def run(self) -> None:
        """서비스 실행 (메인 루프)"""
        if not await self.start():
            return
        
        try:
            # 서비스가 중지될 때까지 대기
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            self.logger.info("🛑 Keyboard interrupt received")
        finally:
            await self.stop()
    
    # =============================================================================
    # 메시지 처리
    # =============================================================================
    
    async def _handle_websocket_message(self, message: ProxyMessage) -> None:
        """WebSocket 메시지 처리"""
        try:
            self.total_messages_received += 1
            
            # 구독 관리자에 알림
            if self.subscription_manager:
                await self.subscription_manager.handle_message(message)
            
            # 워커 풀로 메시지 전달
            if self.message_bridge:
                if await self.message_bridge.add_message(message):
                    self.total_messages_processed += 1
                else:
                    self.logger.warning("Failed to add message to bridge queue")
            
        except Exception as e:
            self.logger.error(f"❌ Message handling error: {e}")
    
    async def _on_subscription_success(self, subscription_id: str, topic: str) -> None:
        """구독 성공 콜백"""
        self.logger.info(f"🎉 Subscription successful: {topic} (ID: {subscription_id})")
    
    async def _on_subscription_failure(self, subscription_id: str, topic: str, error: str) -> None:
        """구독 실패 콜백"""
        self.logger.error(f"❌ Subscription failed: {topic} (ID: {subscription_id}) - {error}")
    
    async def _on_message_received(self, subscription_id: str, message: ProxyMessage) -> None:
        """메시지 수신 콜백"""
        # 추가적인 메시지 처리 로직이 필요한 경우 여기에 구현
        pass
    
    # =============================================================================
    # 헬스 모니터링 콜백
    # =============================================================================
    
    async def _on_health_status_change(self, previous_status: HealthStatus, 
                                     current_status: HealthStatus, metrics) -> None:
        """헬스 상태 변화 콜백"""
        self.logger.info(f"🔄 Health status changed: {previous_status} → {current_status}")
        
        # 상태에 따른 추가 액션
        if current_status == HealthStatus.CRITICAL:
            self.logger.error("🚨 Service is in critical state!")
        elif current_status == HealthStatus.WARNING:
            self.logger.warning("⚠️ Service has warning conditions")
        elif current_status == HealthStatus.HEALTHY:
            self.logger.info("💚 Service is healthy")
    
    async def _on_critical_error(self, metrics) -> None:
        """심각한 오류 콜백"""
        self.logger.critical("🚨 Critical error detected - service may need manual intervention")
        
        # 필요한 경우 여기에 알림 발송 로직 추가
        # - 이메일, Slack, SMS 등
        
        # 극단적인 경우 서비스 재시작
        # await self.restart_service()
    
    async def _on_recovery_needed(self, recovery_actions: list, metrics) -> None:
        """복구 필요 콜백"""
        self.logger.info(f"🔧 Recovery actions executed: {', '.join(recovery_actions)}")
    
    # =============================================================================
    # 구독 관리 API
    # =============================================================================
    
    async def subscribe_to_stock(self, symbol: str, market: str = "kr") -> Optional[str]:
        """주식 구독"""
        if not self.subscription_manager:
            self.logger.error("Subscription manager not available")
            return None
        
        try:
            subscription_id = await self.subscription_manager.subscribe_to_stock(symbol, market)
            self.logger.info(f"📈 Stock subscription requested: {symbol} ({market}) - ID: {subscription_id}")
            return subscription_id
        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe to stock {symbol}: {e}")
            return None
    
    async def unsubscribe_from_stock(self, symbol: str, market: str = "kr") -> bool:
        """주식 구독 해제"""
        if not self.subscription_manager:
            self.logger.error("Subscription manager not available")
            return False
        
        try:
            success = await self.subscription_manager.unsubscribe_from_stock(symbol, market)
            if success:
                self.logger.info(f"📉 Stock unsubscription requested: {symbol} ({market})")
            return success
        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe from stock {symbol}: {e}")
            return False
    
    async def bulk_subscribe_stocks(self, symbols: list, market: str = "kr") -> list:
        """여러 주식 일괄 구독"""
        if not self.subscription_manager:
            self.logger.error("Subscription manager not available")
            return []
        
        try:
            subscription_ids = await self.subscription_manager.bulk_subscribe_stocks(symbols, market)
            self.logger.info(f"📈 Bulk subscription completed: {len(subscription_ids)}/{len(symbols)} stocks")
            return subscription_ids
        except Exception as e:
            self.logger.error(f"❌ Bulk subscription failed: {e}")
            return []
    
    async def _setup_default_subscriptions(self) -> None:
        """기본 구독 설정"""
        # 예시: 삼성전자 구독
        await self.subscribe_to_stock("A005930", "kr")  # 삼성전자
        
        # 필요에 따라 다른 기본 구독 추가
        # await self.subscribe_to_stock("A000660", "kr")  # SK하이닉스
    
    # =============================================================================
    # 상태 조회 API
    # =============================================================================
    
    def get_service_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        status = {
            "service": {
                "is_running": self.is_running,
                "uptime_seconds": uptime,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "total_messages_received": self.total_messages_received,
                "total_messages_processed": self.total_messages_processed
            }
        }
        
        # WebSocket 상태
        if self.websocket_client:
            connection_info = self.websocket_client.get_connection_status()
            status["websocket"] = {
                "status": connection_info.status.value,
                "connected_at": connection_info.connected_at.isoformat() if connection_info.connected_at else None,
                "reconnect_attempts": connection_info.reconnect_attempts,
                "active_subscriptions": len(connection_info.active_subscriptions)
            }
        
        # 구독 상태
        if self.subscription_manager:
            status["subscriptions"] = self.subscription_manager.get_subscription_stats()
        
        # 워커 풀 상태
        if self.worker_pool:
            status["workers"] = self.worker_pool.get_pool_stats()
        
        # 헬스 상태
        if self.health_monitor:
            status["health"] = self.health_monitor.get_health_summary()
        
        return status
    
    # =============================================================================
    # 서비스 관리
    # =============================================================================
    
    async def restart_service(self) -> bool:
        """서비스 재시작"""
        self.logger.info("🔄 Restarting service...")
        
        try:
            await self.stop()
            await asyncio.sleep(2.0)  # 잠시 대기
            return await self.start()
        except Exception as e:
            self.logger.error(f"❌ Service restart failed: {e}")
            return False
    
    def set_custom_message_processor(self, processor: Callable) -> None:
        """사용자 정의 메시지 처리기 설정"""
        self.message_processor = processor
        
        # 기존 워커 풀이 있으면 재시작 필요
        if self.worker_pool:
            self.logger.info("🔄 Message processor updated - worker pool restart required")
    
    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """쿠키 업데이트"""
        if self.websocket_client:
            self.websocket_client.update_cookies(cookies)
            self.logger.info(f"🍪 Cookies updated: {list(cookies.keys())}")


# =============================================================================
# 편의 함수들
# =============================================================================

async def create_and_run_proxy_service(message_processor: Optional[Callable] = None) -> TossProxyService:
    """프록시 서비스 생성 및 실행"""
    service = TossProxyService(message_processor)
    await service.run()
    return service


def run_proxy_service(message_processor: Optional[Callable] = None) -> None:
    """프록시 서비스 실행 (동기 함수)"""
    try:
        asyncio.run(create_and_run_proxy_service(message_processor))
    except KeyboardInterrupt:
        print("\n🛑 Service interrupted by user")
    except Exception as e:
        print(f"❌ Service error: {e}")
        sys.exit(1)
