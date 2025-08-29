"""
WebSocket 관리 컨트롤러

실시간 WebSocket 서비스 상태 확인 및 관리 기능 제공
동적 구독/구독해제 기능 포함
"""
import logging
from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, List

from app.config.get_current_user import get_current_user
from app.services.redis_service import get_redis_service, RedisService
from app.services.toss_websocket_command_service import get_toss_websocket_command_service, TossWebSocketCommandService
from app.utils.response_helper import create_response

router = APIRouter(tags=["TossWebSocketRelayer"])
logger = logging.getLogger(__name__)


@router.get("/toss-ws-relayer/daemon/health", summary="WebSocket 데몬 상태 확인")
async def get_daemon_health(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬의 상태를 확인합니다
    
       - 30초 이상 업데이트 없으면 stale
       - 1분 이상 업데이트 없으면 dead로 간주
    """
    
    health_data = await redis_service.get_toss_ws_relayer_health()
    
    if health_data:
        return create_response(health_data, message="WebSocket 데몬 상태 조회 성공")
    else:
        return create_response(
            {"status": "offline", "message": "WebSocket 데몬이 실행되지 않고 있습니다"},
            message="WebSocket 데몬 오프라인"
        )


@router.get("/toss-ws-relayer/subscriptions", summary="구독 목록 조회")
async def get_subscriptions(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """현재 구독 중인 토픽 목록을 조회합니다 (WebSocket 데몬으로부터)"""
    
    command_service = await get_toss_websocket_command_service(redis_service.redis_client)
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


@router.post("/toss-ws-relayer/subscriptions/subscribe", summary="동적 구독 추가")
async def add_dynamic_subscription(
    topic: str = Query(description="구독할 토픽 (예: /topic/v1/kr/stock/trade/A005930)"),
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬에 새로운 토픽 구독을 동적으로 추가합니다"""
    
    command_service = await get_toss_websocket_command_service(redis_service.redis_client)
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


@router.delete("/toss-ws-relayer/subscriptions/unsubscribe", summary="동적 구독 해제")
async def remove_dynamic_subscription(
    topic: str = Query(description="구독해제할 토픽"),
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬에서 토픽 구독을 동적으로 해제합니다"""
    
    command_service = await get_toss_websocket_command_service(redis_service.redis_client)
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


@router.post("/toss-ws-relayer/reconnect")
async def reconnect_websocket(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
):
    """
    WebSocket 재연결
    
    Toss WebSocket 서버와의 연결이 끊어진 경우 재연결을 시도합니다.
    기존 구독 목록은 자동으로 복원됩니다.
    """
    try:
        logger.info("🔄 WebSocket reconnection API called")
        
        command_service = await get_toss_websocket_command_service(redis_service.redis_client)
        result = await command_service.send_reconnect_command()
        
        if result.get('success'):
            return create_response({
                "success": True,
                "message": "WebSocket 재연결 성공",
                "connection_status": result.get('connection_status', {}),
                "command_id": result.get('command_id')
            })
        else:
            return create_response({
                "success": False,
                "message": result.get('message', 'WebSocket 재연결 실패'),
                "connection_status": result.get('connection_status', {}),
                "command_id": result.get('command_id')
            })
            
    except Exception as e:
        logger.error(f"❌ WebSocket reconnection API error: {e}")
        return create_response({
            "success": False,
            "message": "재연결 요청 실패",
            "error": str(e)
        })
