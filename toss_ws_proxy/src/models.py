"""
Data models for Toss WebSocket Proxy Service
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """메시지 타입"""
    STOCK_TRADE = "stock_trade"
    SUBSCRIPTION_REQUEST = "subscription_request"
    SUBSCRIPTION_RESPONSE = "subscription_response"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    CONNECTION_STATUS = "connection_status"


class ConnectionStatus(str, Enum):
    """연결 상태"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class STOMPFrame(BaseModel):
    """STOMP 프레임 모델"""
    command: str
    headers: Dict[str, str] = {}
    body: str = ""


class SubscriptionRequest(BaseModel):
    """구독 요청 모델"""
    topic: str
    subscription_id: Optional[str] = None
    auto_generate_id: bool = True


class ProxyMessage(BaseModel):
    """프록시 메시지 모델"""
    message_type: MessageType
    timestamp: datetime
    data: Dict[str, Any]
    subscription_id: Optional[str] = None
    topic: Optional[str] = None


class ConnectionInfo(BaseModel):
    """연결 정보 모델"""
    status: ConnectionStatus
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    reconnect_attempts: int = 0
    active_subscriptions: Dict[str, str] = {}  # subscription_id -> topic
    
    
class TossAuthInfo(BaseModel):
    """Toss 인증 정보"""
    authorization: Optional[str] = None
    utk_token: Optional[str] = None
    cookies: Dict[str, str] = {}
    expires_at: Optional[datetime] = None
