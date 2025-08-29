"""
실시간 데이터 컨트롤러

독립 WebSocket 데몬으로부터 Redis를 통해 실시간 주식 데이터 조회
"""
from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, List, Optional

from app.config.get_current_user import get_current_user
from app.services.redis_service import get_redis_service, RedisService
from app.utils.response_helper import create_response

router = APIRouter(tags=["실시간 데이터"])


@router.get("/realtime/stock/{stock_code}", summary="실시간 주가 조회")
async def get_realtime_stock_price(
    stock_code: str,
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """특정 종목의 실시간 주가 데이터를 조회합니다"""
    
    stock_data = await redis_service.get_realtime_stock_data(stock_code)
    
    if stock_data:
        # 응답 데이터 정리
        response_data = {
            "stock_code": stock_code,
            "current_price": stock_data.get('data', {}).get('close'),
            "volume": stock_data.get('data', {}).get('volume'),
            "trade_type": stock_data.get('data', {}).get('tradeType'),
            "change_type": stock_data.get('data', {}).get('changeType'),
            "timestamp": stock_data.get('data', {}).get('dt'),
            "daemon_timestamp": stock_data.get('daemon_timestamp'),
            "subscription": stock_data.get('subscription'),
            "raw_data": stock_data.get('data', {})
        }
        
        return create_response(response_data, message="실시간 주가 조회 성공")
    else:
        return create_response(
            {"stock_code": stock_code, "message": "실시간 데이터가 없습니다"},
            message="실시간 데이터 없음"
        )


@router.get("/realtime/stocks/multiple", summary="여러 종목 실시간 주가 조회")
async def get_multiple_realtime_stocks(
    stock_codes: List[str] = Query(description="조회할 종목 코드 목록 (예: A005930,A000660)"),
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """여러 종목의 실시간 주가 데이터를 한 번에 조회합니다"""
    
    stocks_data = await redis_service.get_multiple_realtime_data(stock_codes)
    
    # 응답 데이터 정리
    response_data = {}
    for stock_code, stock_data in stocks_data.items():
        if stock_data:
            response_data[stock_code] = {
                "current_price": stock_data.get('data', {}).get('close'),
                "volume": stock_data.get('data', {}).get('volume'),
                "trade_type": stock_data.get('data', {}).get('tradeType'),
                "change_type": stock_data.get('data', {}).get('changeType'),
                "timestamp": stock_data.get('data', {}).get('dt'),
                "daemon_timestamp": stock_data.get('daemon_timestamp')
            }
        else:
            response_data[stock_code] = None
    
    return create_response(
        {
            "stocks": response_data,
            "total_count": len(stock_codes),
            "available_count": len([d for d in response_data.values() if d is not None])
        },
        message="여러 종목 실시간 주가 조회 성공"
    )


@router.get("/realtime/stocks/all", summary="모든 실시간 종목 조회")
async def get_all_realtime_stocks(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """현재 실시간 데이터가 있는 모든 종목을 조회합니다"""
    
    stock_codes = await redis_service.get_all_realtime_stocks()
    
    if stock_codes:
        # 모든 종목의 데이터 조회
        stocks_data = await redis_service.get_multiple_realtime_data(stock_codes)
        
        # 응답 데이터 정리
        response_data = []
        for stock_code, stock_data in stocks_data.items():
            if stock_data:
                response_data.append({
                    "stock_code": stock_code,
                    "current_price": stock_data.get('data', {}).get('close'),
                    "volume": stock_data.get('data', {}).get('volume'),
                    "trade_type": stock_data.get('data', {}).get('tradeType'),
                    "change_type": stock_data.get('data', {}).get('changeType'),
                    "timestamp": stock_data.get('data', {}).get('dt'),
                    "daemon_timestamp": stock_data.get('daemon_timestamp')
                })
        
        return create_response(
            {
                "stocks": response_data,
                "total_count": len(response_data)
            },
            message="전체 실시간 종목 조회 성공"
        )
    else:
        return create_response(
            {"stocks": [], "total_count": 0},
            message="실시간 데이터가 있는 종목이 없습니다"
        )


@router.get("/realtime/daemon/health", summary="WebSocket 데몬 상태 확인")
async def get_daemon_health(
    current_user_id: str = Depends(get_current_user),
    redis_service: RedisService = Depends(get_redis_service)
) -> Dict[str, Any]:
    """WebSocket 데몬의 상태를 확인합니다"""
    
    health_data = await redis_service.get_toss_ws_relayer_health()
    
    if health_data:
        return create_response(health_data, message="WebSocket 데몬 상태 조회 성공")
    else:
        return create_response(
            {"status": "offline", "message": "WebSocket 데몬이 실행되지 않고 있습니다"},
            message="WebSocket 데몬 오프라인"
        )
