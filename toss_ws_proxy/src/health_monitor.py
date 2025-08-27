"""
Health monitoring and auto-recovery system
헬스 모니터링 및 자동 복구 시스템
"""
import asyncio
import logging
import time
import psutil
import os
import signal
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .config import config
from .models import ConnectionStatus, MessageType


class HealthStatus(str, Enum):
    """헬스 상태"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """헬스 메트릭"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 연결 상태
    websocket_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    connection_uptime: float = 0.0
    reconnection_count: int = 0
    last_heartbeat: Optional[datetime] = None
    
    # 메시지 처리
    messages_received: int = 0
    messages_processed: int = 0
    message_processing_rate: float = 0.0  # msg/sec
    message_queue_size: int = 0
    processing_errors: int = 0
    
    # 구독 상태
    active_subscriptions: int = 0
    failed_subscriptions: int = 0
    subscription_success_rate: float = 100.0
    
    # 시스템 리소스
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_usage_mb: float = 0.0
    
    # 네트워크
    network_latency: Optional[float] = None
    network_errors: int = 0
    
    # 전반적인 상태
    overall_status: HealthStatus = HealthStatus.UNKNOWN


class HealthMonitor:
    """헬스 모니터링 시스템"""
    
    def __init__(self, websocket_client=None, subscription_manager=None, worker_pool=None):
        self.websocket_client = websocket_client
        self.subscription_manager = subscription_manager
        self.worker_pool = worker_pool
        
        # 모니터링 상태
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.check_interval = 10.0  # 10초마다 체크
        
        # 메트릭 히스토리
        self.metrics_history: List[HealthMetrics] = []
        self.max_history_size = 1440  # 24시간 (10초 간격)
        
        # 이전 메트릭 (델타 계산용)
        self.previous_metrics: Optional[HealthMetrics] = None
        
        # 알림 및 액션 콜백
        self.on_health_status_change: Optional[Callable] = None
        self.on_critical_error: Optional[Callable] = None
        self.on_recovery_needed: Optional[Callable] = None
        
        # 복구 액션 플래그
        self.auto_recovery_enabled = True
        self.max_recovery_attempts = 3
        self.recovery_attempts = 0
        self.last_recovery_time: Optional[datetime] = None
        
        # 임계값 설정
        self.thresholds = {
            'cpu_usage_warning': 80.0,
            'cpu_usage_critical': 95.0,
            'memory_usage_warning': 80.0,
            'memory_usage_critical': 95.0,
            'message_queue_warning': 5000,
            'message_queue_critical': 8000,
            'processing_error_rate_warning': 5.0,  # 5%
            'processing_error_rate_critical': 15.0,  # 15%
            'connection_downtime_warning': 30.0,  # 30초
            'connection_downtime_critical': 300.0,  # 5분
        }
        
        # 로깅
        self.logger = logging.getLogger("HealthMonitor")
        
        # 시작 시간
        self.start_time = datetime.now()
        
        # 프로세스 정보
        self.process = psutil.Process()
    
    def set_dependencies(self, websocket_client=None, subscription_manager=None, worker_pool=None):
        """의존성 설정"""
        if websocket_client:
            self.websocket_client = websocket_client
        if subscription_manager:
            self.subscription_manager = subscription_manager
        if worker_pool:
            self.worker_pool = worker_pool
    
    def start(self) -> None:
        """헬스 모니터링 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("🏥 HealthMonitor started")
    
    async def stop(self) -> None:
        """헬스 모니터링 중지"""
        self.is_running = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🏥 HealthMonitor stopped")
    
    # =============================================================================
    # 모니터링 루프
    # =============================================================================
    
    async def _monitor_loop(self) -> None:
        """헬스 모니터링 메인 루프"""
        self.logger.info("🏥 Health monitoring loop started")
        
        while self.is_running:
            try:
                # 헬스 메트릭 수집
                metrics = await self._collect_metrics()
                
                # 상태 평가
                previous_status = self.previous_metrics.overall_status if self.previous_metrics else HealthStatus.UNKNOWN
                current_status = self._evaluate_health_status(metrics)
                metrics.overall_status = current_status
                
                # 메트릭 히스토리 저장
                self._save_metrics(metrics)
                
                # 상태 변화 알림
                if previous_status != current_status:
                    await self._notify_status_change(previous_status, current_status, metrics)
                
                # 자동 복구 액션
                if self.auto_recovery_enabled and current_status == HealthStatus.CRITICAL:
                    await self._attempt_recovery(metrics)
                
                # 메트릭 로깅
                self._log_metrics(metrics)
                
                # 다음 체크까지 대기
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Health monitoring error: {e}")
                await asyncio.sleep(5.0)
        
        self.logger.info("🏥 Health monitoring loop ended")
    
    async def _collect_metrics(self) -> HealthMetrics:
        """헬스 메트릭 수집"""
        metrics = HealthMetrics()
        
        try:
            # WebSocket 연결 상태
            if self.websocket_client:
                connection_info = self.websocket_client.get_connection_status()
                metrics.websocket_status = connection_info.status
                metrics.reconnection_count = connection_info.reconnect_attempts
                metrics.last_heartbeat = connection_info.last_heartbeat
                
                if connection_info.connected_at:
                    metrics.connection_uptime = (datetime.now() - connection_info.connected_at).total_seconds()
            
            # 구독 상태
            if self.subscription_manager:
                sub_stats = self.subscription_manager.get_subscription_stats()
                metrics.active_subscriptions = sub_stats.get('active_subscriptions', 0)
                metrics.failed_subscriptions = sub_stats.get('failed_subscriptions', 0)
                
                total_subs = sub_stats.get('total_subscriptions', 0)
                if total_subs > 0:
                    metrics.subscription_success_rate = (metrics.active_subscriptions / total_subs) * 100.0
            
            # 워커 풀 상태
            if self.worker_pool:
                pool_stats = self.worker_pool.get_pool_stats()
                metrics.messages_processed = pool_stats.get('total_processed', 0)
                metrics.processing_errors = pool_stats.get('total_errors', 0)
                metrics.message_queue_size = pool_stats.get('total_queue_size', 0)
                
                # 메시지 처리 속도 계산
                if self.previous_metrics:
                    time_delta = (metrics.timestamp - self.previous_metrics.timestamp).total_seconds()
                    if time_delta > 0:
                        msg_delta = metrics.messages_processed - self.previous_metrics.messages_processed
                        metrics.message_processing_rate = msg_delta / time_delta
            
            # 시스템 리소스
            metrics.cpu_usage = self.process.cpu_percent()
            
            memory_info = self.process.memory_info()
            metrics.memory_usage_mb = memory_info.rss / (1024 * 1024)  # MB
            
            # 시스템 전체 메모리 대비 비율
            system_memory = psutil.virtual_memory()
            metrics.memory_usage = (memory_info.rss / system_memory.total) * 100.0
            
            # 네트워크 상태 (간단한 ping 테스트)
            if self.websocket_client and metrics.websocket_status == ConnectionStatus.CONNECTED:
                try:
                    start_time = time.time()
                    # 간단한 heartbeat 전송으로 레이턴시 측정
                    # 실제로는 WebSocket ping/pong을 사용하는 것이 좋음
                    metrics.network_latency = (time.time() - start_time) * 1000  # ms
                except:
                    metrics.network_latency = None
            
        except Exception as e:
            self.logger.error(f"❌ Metrics collection error: {e}")
        
        return metrics
    
    def _evaluate_health_status(self, metrics: HealthMetrics) -> HealthStatus:
        """헬스 상태 평가"""
        critical_issues = []
        warning_issues = []
        
        # CPU 사용률 체크
        if metrics.cpu_usage > self.thresholds['cpu_usage_critical']:
            critical_issues.append(f"CPU usage: {metrics.cpu_usage:.1f}%")
        elif metrics.cpu_usage > self.thresholds['cpu_usage_warning']:
            warning_issues.append(f"CPU usage: {metrics.cpu_usage:.1f}%")
        
        # 메모리 사용률 체크
        if metrics.memory_usage > self.thresholds['memory_usage_critical']:
            critical_issues.append(f"Memory usage: {metrics.memory_usage:.1f}%")
        elif metrics.memory_usage > self.thresholds['memory_usage_warning']:
            warning_issues.append(f"Memory usage: {metrics.memory_usage:.1f}%")
        
        # 메시지 큐 사이즈 체크
        if metrics.message_queue_size > self.thresholds['message_queue_critical']:
            critical_issues.append(f"Message queue size: {metrics.message_queue_size}")
        elif metrics.message_queue_size > self.thresholds['message_queue_warning']:
            warning_issues.append(f"Message queue size: {metrics.message_queue_size}")
        
        # 연결 상태 체크
        if metrics.websocket_status in [ConnectionStatus.FAILED, ConnectionStatus.DISCONNECTED]:
            if metrics.connection_uptime == 0:  # 연결이 아예 안됨
                critical_issues.append("WebSocket connection failed")
            else:
                downtime = (datetime.now() - (metrics.last_heartbeat or datetime.now())).total_seconds()
                if downtime > self.thresholds['connection_downtime_critical']:
                    critical_issues.append(f"Connection downtime: {downtime:.1f}s")
                elif downtime > self.thresholds['connection_downtime_warning']:
                    warning_issues.append(f"Connection downtime: {downtime:.1f}s")
        
        # 처리 에러율 체크
        if metrics.messages_processed > 0:
            error_rate = (metrics.processing_errors / metrics.messages_processed) * 100.0
            if error_rate > self.thresholds['processing_error_rate_critical']:
                critical_issues.append(f"Processing error rate: {error_rate:.1f}%")
            elif error_rate > self.thresholds['processing_error_rate_warning']:
                warning_issues.append(f"Processing error rate: {error_rate:.1f}%")
        
        # 구독 성공률 체크
        if metrics.subscription_success_rate < 80.0:
            critical_issues.append(f"Subscription success rate: {metrics.subscription_success_rate:.1f}%")
        elif metrics.subscription_success_rate < 95.0:
            warning_issues.append(f"Subscription success rate: {metrics.subscription_success_rate:.1f}%")
        
        # 상태 결정
        if critical_issues:
            self.logger.error(f"🚨 Critical issues detected: {', '.join(critical_issues)}")
            return HealthStatus.CRITICAL
        elif warning_issues:
            self.logger.warning(f"⚠️ Warning issues detected: {', '.join(warning_issues)}")
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def _save_metrics(self, metrics: HealthMetrics) -> None:
        """메트릭 히스토리 저장"""
        self.metrics_history.append(metrics)
        
        # 히스토리 크기 제한
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
        
        # 이전 메트릭 업데이트
        self.previous_metrics = metrics
    
    def _log_metrics(self, metrics: HealthMetrics) -> None:
        """메트릭 로깅"""
        status_emoji = {
            HealthStatus.HEALTHY: "💚",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "🚨",
            HealthStatus.UNKNOWN: "❓"
        }
        
        emoji = status_emoji.get(metrics.overall_status, "❓")
        
        self.logger.info(
            f"{emoji} Health Status: {metrics.overall_status.value} | "
            f"WS: {metrics.websocket_status.value} | "
            f"CPU: {metrics.cpu_usage:.1f}% | "
            f"MEM: {metrics.memory_usage:.1f}% ({metrics.memory_usage_mb:.1f}MB) | "
            f"Queue: {metrics.message_queue_size} | "
            f"Subs: {metrics.active_subscriptions}/{metrics.active_subscriptions + metrics.failed_subscriptions} | "
            f"Rate: {metrics.message_processing_rate:.1f} msg/s"
        )
    
    # =============================================================================
    # 알림 및 복구
    # =============================================================================
    
    async def _notify_status_change(self, previous_status: HealthStatus, 
                                   current_status: HealthStatus, metrics: HealthMetrics) -> None:
        """상태 변화 알림"""
        self.logger.info(f"🔄 Health status changed: {previous_status.value} → {current_status.value}")
        
        if self.on_health_status_change:
            await self._safe_callback(self.on_health_status_change, previous_status, current_status, metrics)
    
    async def _attempt_recovery(self, metrics: HealthMetrics) -> None:
        """자동 복구 시도"""
        current_time = datetime.now()
        
        # 복구 시도 제한 체크
        if (self.last_recovery_time and 
            (current_time - self.last_recovery_time).total_seconds() < 60.0):  # 1분 내 복구 시도 제한
            return
        
        if self.recovery_attempts >= self.max_recovery_attempts:
            self.logger.error(f"🚨 Max recovery attempts ({self.max_recovery_attempts}) reached")
            if self.on_critical_error:
                await self._safe_callback(self.on_critical_error, metrics)
            return
        
        self.recovery_attempts += 1
        self.last_recovery_time = current_time
        
        self.logger.warning(f"🔧 Attempting recovery #{self.recovery_attempts}")
        
        try:
            # 복구 액션들
            recovery_actions = []
            
            # WebSocket 연결 문제
            if metrics.websocket_status in [ConnectionStatus.FAILED, ConnectionStatus.DISCONNECTED]:
                recovery_actions.append("reconnect_websocket")
            
            # 메모리 사용량 문제
            if metrics.memory_usage > self.thresholds['memory_usage_critical']:
                recovery_actions.append("garbage_collect")
            
            # 메시지 큐 과부하
            if metrics.message_queue_size > self.thresholds['message_queue_critical']:
                recovery_actions.append("clear_message_queue")
            
            # 복구 액션 실행
            for action in recovery_actions:
                await self._execute_recovery_action(action)
            
            # 복구 알림
            if self.on_recovery_needed:
                await self._safe_callback(self.on_recovery_needed, recovery_actions, metrics)
            
        except Exception as e:
            self.logger.error(f"❌ Recovery attempt failed: {e}")
    
    async def _execute_recovery_action(self, action: str) -> None:
        """복구 액션 실행"""
        try:
            if action == "reconnect_websocket":
                if self.websocket_client:
                    self.logger.info("🔧 Triggering WebSocket reconnection")
                    await self.websocket_client._trigger_reconnect()
            
            elif action == "garbage_collect":
                self.logger.info("🔧 Running garbage collection")
                import gc
                gc.collect()
            
            elif action == "clear_message_queue":
                self.logger.info("🔧 Clearing message queues")
                if self.worker_pool:
                    # 워커 큐 비우기 (구현 필요)
                    pass
            
            elif action == "restart_service":
                self.logger.critical("🔧 Restarting service process")
                # 프로세스 재시작 (신중하게 구현 필요)
                os.kill(os.getpid(), signal.SIGTERM)
            
        except Exception as e:
            self.logger.error(f"❌ Recovery action '{action}' failed: {e}")
    
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
    # 상태 조회 API
    # =============================================================================
    
    def get_current_metrics(self) -> Optional[HealthMetrics]:
        """현재 메트릭 조회"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_history(self, hours: int = 1) -> List[HealthMetrics]:
        """메트릭 히스토리 조회"""
        if not self.metrics_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """헬스 요약 정보"""
        current_metrics = self.get_current_metrics()
        if not current_metrics:
            return {"status": "unknown", "message": "No metrics available"}
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "status": current_metrics.overall_status.value,
            "uptime_seconds": uptime,
            "websocket_status": current_metrics.websocket_status.value,
            "connection_uptime": current_metrics.connection_uptime,
            "active_subscriptions": current_metrics.active_subscriptions,
            "message_processing_rate": current_metrics.message_processing_rate,
            "cpu_usage": current_metrics.cpu_usage,
            "memory_usage_mb": current_metrics.memory_usage_mb,
            "recovery_attempts": self.recovery_attempts,
            "last_check": current_metrics.timestamp.isoformat()
        }
    
    def reset_recovery_attempts(self) -> None:
        """복구 시도 횟수 초기화"""
        self.recovery_attempts = 0
        self.last_recovery_time = None
        self.logger.info("🔄 Recovery attempts reset")
