"""
Worker threads for processing WebSocket messages
메시지 처리를 위한 워커 스레드 시스템
"""
import asyncio
import threading
import json
import logging
from typing import Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
import time
from datetime import datetime

from .config import config
from .models import ProxyMessage, MessageType


class MessageWorker:
    """메시지 처리 워커"""
    
    def __init__(self, worker_id: int, message_processor: Optional[Callable] = None):
        self.worker_id = worker_id
        self.message_processor = message_processor or self._default_processor
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.message_queue: Queue = Queue(maxsize=config.max_message_queue_size)
        
        # 통계
        self.processed_count = 0
        self.error_count = 0
        self.last_processed_at: Optional[datetime] = None
        
        # 로깅
        self.logger = logging.getLogger(f"MessageWorker-{worker_id}")
    
    def start(self) -> None:
        """워커 스레드 시작"""
        if self.is_running:
            self.logger.warning("Worker already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"🚀 MessageWorker-{self.worker_id} started")
    
    def stop(self, timeout: float = 5.0) -> None:
        """워커 스레드 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 종료 신호를 위한 특별한 메시지 추가
        try:
            self.message_queue.put(None, timeout=1.0)
        except:
            pass
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
            
        self.logger.info(f"🛑 MessageWorker-{self.worker_id} stopped")
    
    def add_message(self, message: ProxyMessage, timeout: float = 1.0) -> bool:
        """메시지를 워커 큐에 추가"""
        try:
            self.message_queue.put(message, timeout=timeout)
            return True
        except:
            self.logger.warning(f"Failed to add message to worker queue (worker {self.worker_id})")
            return False
    
    def _worker_loop(self) -> None:
        """워커 메인 루프"""
        self.logger.info(f"💼 Worker {self.worker_id} loop started")
        
        while self.is_running:
            try:
                # 메시지 가져오기 (1초 타임아웃)
                message = self.message_queue.get(timeout=1.0)
                
                # 종료 신호 확인
                if message is None:
                    break
                
                # 메시지 처리
                self._process_message(message)
                
            except Empty:
                # 타임아웃은 정상적인 상황
                continue
            except Exception as e:
                self.logger.error(f"❌ Worker loop error: {e}")
                self.error_count += 1
                time.sleep(0.1)  # 에러 시 잠시 대기
        
        self.logger.info(f"💼 Worker {self.worker_id} loop ended")
    
    def _process_message(self, message: ProxyMessage) -> None:
        """개별 메시지 처리"""
        try:
            start_time = time.time()
            
            # 메시지 처리
            self.message_processor(message)
            
            # 통계 업데이트
            self.processed_count += 1
            self.last_processed_at = datetime.now()
            
            processing_time = time.time() - start_time
            if processing_time > 0.1:  # 100ms 이상 걸린 경우 로그
                self.logger.warning(f"Slow message processing: {processing_time:.3f}s")
                
        except Exception as e:
            self.logger.error(f"❌ Message processing error: {e}")
            self.error_count += 1
    
    def _default_processor(self, message: ProxyMessage) -> None:
        """기본 메시지 처리기"""
        self.logger.info(f"📨 [Worker-{self.worker_id}] Processed message:")
        self.logger.info(f"   Type: {message.message_type}")
        self.logger.info(f"   Topic: {message.topic}")
        self.logger.info(f"   Timestamp: {message.timestamp}")
        self.logger.info(f"   Data keys: {list(message.data.keys())}")
        
        # 실제 데이터가 있는 경우 일부만 출력
        if message.data.get('body'):
            body = message.data['body']
            if len(body) > 200:
                body = body[:200] + "..."
            self.logger.info(f"   Body preview: {body}")
    
    def get_stats(self) -> dict:
        """워커 통계 정보"""
        return {
            "worker_id": self.worker_id,
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "queue_size": self.message_queue.qsize(),
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None
        }


class WorkerPool:
    """워커 풀 관리자"""
    
    def __init__(self, message_processor: Optional[Callable] = None):
        self.workers: list[MessageWorker] = []
        self.message_processor = message_processor
        self.current_worker_index = 0
        
        # 로깅
        self.logger = logging.getLogger("WorkerPool")
        
        # 워커 생성
        for i in range(config.worker_thread_count):
            worker = MessageWorker(i, message_processor)
            self.workers.append(worker)
    
    def start(self) -> None:
        """모든 워커 시작"""
        for worker in self.workers:
            worker.start()
        self.logger.info(f"🚀 WorkerPool started with {len(self.workers)} workers")
    
    def stop(self, timeout: float = 10.0) -> None:
        """모든 워커 중지"""
        self.logger.info("🛑 Stopping WorkerPool...")
        
        for worker in self.workers:
            worker.stop(timeout=timeout / len(self.workers))
        
        self.logger.info("🛑 WorkerPool stopped")
    
    def distribute_message(self, message: ProxyMessage) -> bool:
        """메시지를 워커에게 라운드 로빈 방식으로 분배"""
        if not self.workers:
            self.logger.error("No workers available")
            return False
        
        # 라운드 로빈으로 워커 선택
        worker = self.workers[self.current_worker_index]
        self.current_worker_index = (self.current_worker_index + 1) % len(self.workers)
        
        return worker.add_message(message)
    
    def get_pool_stats(self) -> dict:
        """워커 풀 전체 통계"""
        total_processed = sum(w.processed_count for w in self.workers)
        total_errors = sum(w.error_count for w in self.workers)
        total_queue_size = sum(w.message_queue.qsize() for w in self.workers)
        
        return {
            "worker_count": len(self.workers),
            "total_processed": total_processed,
            "total_errors": total_errors,
            "total_queue_size": total_queue_size,
            "workers": [w.get_stats() for w in self.workers]
        }


class AsyncMessageBridge:
    """비동기 메시지 브리지 - asyncio와 thread 간 메시지 전달"""
    
    def __init__(self, worker_pool: WorkerPool):
        self.worker_pool = worker_pool
        self.async_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_message_queue_size * 2)
        self.bridge_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 로깅
        self.logger = logging.getLogger("AsyncMessageBridge")
    
    def start(self) -> None:
        """브리지 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self.bridge_task = asyncio.create_task(self._bridge_loop())
        self.logger.info("🌉 AsyncMessageBridge started")
    
    async def stop(self) -> None:
        """브리지 중지"""
        self.is_running = False
        
        if self.bridge_task and not self.bridge_task.done():
            self.bridge_task.cancel()
            try:
                await self.bridge_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🌉 AsyncMessageBridge stopped")
    
    async def add_message(self, message: ProxyMessage) -> bool:
        """비동기 큐에 메시지 추가"""
        try:
            self.async_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            self.logger.warning("Async message queue is full")
            return False
    
    async def _bridge_loop(self) -> None:
        """브리지 메인 루프"""
        self.logger.info("🌉 Bridge loop started")
        
        while self.is_running:
            try:
                # 비동기 큐에서 메시지 가져오기
                message = await asyncio.wait_for(self.async_queue.get(), timeout=1.0)
                
                # 워커 풀에 전달 (논블로킹)
                if not self.worker_pool.distribute_message(message):
                    self.logger.warning("Failed to distribute message to worker pool")
                
            except asyncio.TimeoutError:
                # 타임아웃은 정상적인 상황
                continue
            except Exception as e:
                self.logger.error(f"❌ Bridge loop error: {e}")
                await asyncio.sleep(0.1)
        
        self.logger.info("🌉 Bridge loop ended")


# =============================================================================
# 사용자 정의 메시지 처리기 예시
# =============================================================================

def custom_stock_processor(message: ProxyMessage) -> None:
    """주식 데이터 처리 예시"""
    try:
        if message.message_type == MessageType.STOCK_TRADE:
            # JSON 파싱 시도
            body = message.data.get('body', '')
            if body:
                try:
                    data = json.loads(body)
                    # 주식 데이터 처리 로직
                    symbol = data.get('symbol', 'unknown')
                    price = data.get('price', 0)
                    volume = data.get('volume', 0)
                    
                    print(f"📈 Stock Update - {symbol}: Price={price}, Volume={volume}")
                    
                    # 여기에 실제 비즈니스 로직 추가
                    # - 데이터베이스 저장
                    # - 알림 발송
                    # - 분석 처리 등
                    
                except json.JSONDecodeError:
                    # JSON이 아닌 경우 원본 텍스트 처리
                    print(f"📊 Raw Stock Data: {body[:100]}...")
        
    except Exception as e:
        logging.getLogger("custom_stock_processor").error(f"Processing error: {e}")


def analytics_processor(message: ProxyMessage) -> None:
    """분석용 메시지 처리기"""
    try:
        # 메시지 통계 수집
        timestamp = message.timestamp
        topic = message.topic or "unknown"
        
        # 간단한 통계 출력
        print(f"📊 Analytics - Topic: {topic}, Time: {timestamp}")
        
        # 실제로는 여기에 분석 로직 추가
        # - 실시간 지표 계산
        # - 트렌드 분석
        # - 알고리즘 트레이딩 신호 생성 등
        
    except Exception as e:
        logging.getLogger("analytics_processor").error(f"Analytics error: {e}")
