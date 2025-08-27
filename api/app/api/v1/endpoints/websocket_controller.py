"""
WebSocket 관리 컨트롤러

실시간 WebSocket 서비스 상태 확인 및 관리 기능 제공
동적 구독/구독해제 기능 포함
"""
from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, List

from app.config.get_current_user import get_current_user
from app.services.redis_service import get_redis_service, RedisService
from app.services.websocket_command_service import get_websocket_command_service, WebSocketCommandService
from app.utils.response_helper import create_response

router = APIRouter(tags=["WebSocket"])


@router.get("/websocket/daemon/health", summary="WebSocket 데몬 상태 확인")
async def get_daemon_health(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬의 상태를 확인합니다"""
    
    health_data = await redis_service.get_websocket_daemon_health()
    
    if health_data:
        return create_response(health_data, message="WebSocket 데몬 상태 조회 성공")
    else:
        return create_response(
            {"status": "offline", "message": "WebSocket 데몬이 실행되지 않고 있습니다"},
            message="WebSocket 데몬 오프라인"
        )


@router.get("/websocket/subscriptions", summary="구독 목록 조회")
async def get_subscriptions(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """현재 구독 중인 토픽 목록을 조회합니다 (WebSocket 데몬으로부터)"""
    
    command_service = await get_websocket_command_service(redis_service.redis_client)
    result = await command_service.get_subscriptions()
    
    if result.get('success'):
        return create_response(
            {
                "subscriptions": result.get('subscriptions', []),
                "total_count": result.get('total_count', 0),
                "websocket_connected": result.get('websocket_connected', False)
            },
            message="구독 목록 조회 성공"
        )
    else:
        return create_response(
            {"error": result.get('message', 'Unknown error')},
            message="구독 목록 조회 실패"
        )


@router.post("/websocket/subscriptions/subscribe", summary="동적 구독 추가")
async def add_dynamic_subscription(
    topic: str = Query(description="구독할 토픽 (예: /topic/v1/kr/stock/trade/A005930)"),
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬에 새로운 토픽 구독을 동적으로 추가합니다"""
    
    command_service = await get_websocket_command_service(redis_service.redis_client)
    result = await command_service.send_subscribe_command(topic)
    
    if result.get('success'):
        return create_response(
            {
                "topic": topic,
                "command_id": result.get('command_id'),
                "message": result.get('message')
            },
            message="구독 추가 성공"
        )
    else:
        return create_response(
            {
                "topic": topic,
                "error": result.get('message', 'Unknown error'),
                "command_id": result.get('command_id')
            },
            message="구독 추가 실패"
        )


@router.delete("/websocket/subscriptions/unsubscribe", summary="동적 구독 해제")
async def remove_dynamic_subscription(
    topic: str = Query(description="구독해제할 토픽"),
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬에서 토픽 구독을 동적으로 해제합니다"""
    
    command_service = await get_websocket_command_service(redis_service.redis_client)
    result = await command_service.send_unsubscribe_command(topic)
    
    if result.get('success'):
        return create_response(
            {
                "topic": topic,
                "command_id": result.get('command_id'),
                "message": result.get('message')
            },
            message="구독 해제 성공"
        )
    else:
        return create_response(
            {
                "topic": topic,
                "error": result.get('message', 'Unknown error'),
                "command_id": result.get('command_id')
            },
            message="구독 해제 실패"
        )
