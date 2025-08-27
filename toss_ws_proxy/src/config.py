"""
Configuration settings for Toss WebSocket Proxy Service
"""
import os
from typing import Dict, Any
from pydantic import BaseSettings


class TossProxyConfig(BaseSettings):
    """Toss WebSocket Proxy 설정"""
    
    # WebSocket 연결 설정
    websocket_url: str = "wss://realtime-socket.tossinvest.com/ws"
    connection_timeout: float = 15.0
    heartbeat_interval: float = 4.0
    
    # 재연결 설정
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 5.0
    reconnect_backoff_multiplier: float = 1.5
    
    # 데이터 처리 설정
    max_message_queue_size: int = 10000
    worker_thread_count: int = 2
    
    # Toss API 설정
    device_id: str = "WTS-6857e1aa2ef34224a9ccfb6f879c1c1e"
    refresh_token_url: str = "https://wts-api.tossinvest.com/api/v1/refresh-utk"
    
    # 기본 쿠키 설정
    default_cookies: Dict[str, str] = {
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
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_prefix = "TOSS_PROXY_"
        env_file = ".env"


# 전역 설정 인스턴스
config = TossProxyConfig()
