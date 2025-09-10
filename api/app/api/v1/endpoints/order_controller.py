from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.config.db import get_db
from app.config.get_current_user import get_current_user
from app.config.di import get_order_service
from app.services.order_service import OrderService
from app.api.v1.schemas.order_schema import (
    OrderCreate, OrderUpdate, OrderCancel, OrderResponse, OrderWithExecutionsResponse,
    OrderListResponse, OrderSearchRequest, OrderSummaryResponse, QuickOrderRequest
)
from app.db.models.order import OrderStatus, OrderType, OrderMethod
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage
from app.exceptions.custom_exceptions import ValidationError, NotFoundError, InsufficientBalanceError

router = APIRouter()


@router.post("/orders", summary="주문 생성")
async def create_order(
    order_data: OrderCreate,
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    새로운 주문을 생성합니다.
    - 매수/매도 주문 지원
    - 시장가/지정가 주문 지원
    - 손절매/이익실현 주문 지원
    """
    try:
        # Pydantic이 모델 Enum으로 파싱하므로 그대로 전달
        order = order_service.create_order(current_user_id, order_data.model_dump(mode='python'))
        order_response = OrderResponse.model_validate(order)
        
        return create_response(
            data=order_response.model_dump(),
            status_code=201,
            message="주문이 성공적으로 생성되었습니다."
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 생성 실패: {str(e)}")


@router.get("/orders", response_model=OrderListResponse, summary="주문 조회")
async def get_orders(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    
    # 상태/타입 필터
    status: Optional[OrderStatus] = Query(None, description="주문 상태"),
    order_type: Optional[OrderType] = Query(None, description="주문 유형"),
    stock_id: Optional[str] = Query(None, description="주식 종목 ID"),
    
    # 날짜 필터
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    
    # 히스토리 모드
    history_only: bool = Query(False, description="완료된 주문만 조회 (FILLED, CANCELLED, REJECTED, EXPIRED)"),
    
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    사용자의 주문을 조회합니다.
    
    ## 조회 모드:
    - **일반 모드** (history_only=false): 모든 상태의 주문 조회
    - **히스토리 모드** (history_only=true): 완료된 주문만 조회
    
    ## 주문 상태:
    - PENDING: 대기중
    - PARTIALLY_FILLED: 부분체결
    - FILLED: 체결완료
    - CANCELLED: 취소됨
    - REJECTED: 거부됨
    - EXPIRED: 만료됨
    
    ## 필터 옵션:
    - status: 특정 상태 필터링
    - order_type: 매수/매도 필터링
    - stock_id: 특정 종목 필터링
    - start_date/end_date: 날짜 범위 필터링
    """
    try:
        # 날짜 파싱
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
        
        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
        
        # 통합된 주문 조회 서비스 호출
        result = order_service.get_orders_unified(
            user_id=current_user_id,
            page=page,
            size=size,
            status=status,
            order_type=order_type,
            stock_id=stock_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            history_only=history_only
        )
        
        # 주문 응답 변환
        order_responses = [OrderWithExecutionsResponse.model_validate(order) for order in result['orders']]
        
        # SimplePage로 변환
        simple_page = SimplePage(
            items=order_responses,
            page=result['page'],
            per_page=result['size'],
            has_next=result['page'] < result['pages']
        )
        
        paged_response = OrderListResponse.from_page_result(simple_page)
        mode_message = "완료된 주문" if history_only else "주문"
        return create_response(paged_response.model_dump(), message=f"{mode_message} 조회 성공")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 조회 실패: {str(e)}")


@router.get("/orders/summary", response_model=OrderSummaryResponse, summary="주문 요약 정보")
async def get_order_summary(
    period_days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """지정된 기간의 주문 요약 정보를 조회합니다."""
    try:
        summary = order_service.get_order_summary(current_user_id, period_days)
        summary_response = OrderSummaryResponse(**summary)
        
        return create_response(summary_response.model_dump(), message="주문 요약 정보 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 요약 정보 조회 실패: {str(e)}")


@router.get("/orders/pending", response_model=OrderListResponse, summary="대기중인 주문 조회")
async def get_pending_orders(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """현재 대기중인 주문들을 조회합니다."""
    try:
        result = order_service.get_pending_orders(current_user_id, page, size)
        
        # 주문 응답 변환
        order_responses = [OrderWithExecutionsResponse.model_validate(order) for order in result['orders']]
        
        # SimplePage로 변환
        simple_page = SimplePage(
            items=order_responses,
            page=result['page'],
            per_page=result['size'],
            has_next=result['page'] < result['pages']
        )
        
        paged_response = OrderListResponse.from_page_result(simple_page)
        return create_response(paged_response.model_dump(), message="대기중인 주문 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대기중인 주문 조회 실패: {str(e)}")


@router.get("/orders/{order_id}", response_model=OrderWithExecutionsResponse, summary="주문 상세 조회")
async def get_order(
    order_id: str,
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """특정 주문의 상세 정보와 체결 내역을 조회합니다."""
    try:
        order = order_service.get_order_by_id(current_user_id, order_id)
        order_response = OrderWithExecutionsResponse.model_validate(order)
        
        return create_response(order_response.model_dump(), message="주문 상세 조회 성공")
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 상세 조회 실패: {str(e)}")


@router.put("/orders/{order_id}", summary="주문 수정")
async def update_order(
    order_id: str,
    order_data: OrderUpdate,
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    주문을 수정합니다.
    - 대기중인 주문만 수정 가능
    - 가격, 수량, 만료일 수정 가능
    """
    try:
        updated_order = order_service.update_order(
            current_user_id, 
            order_id, 
            order_data.model_dump(exclude_unset=True)
        )
        order_response = OrderResponse.model_validate(updated_order)
        
        return create_response(
            data=order_response.model_dump(),
            message="주문이 성공적으로 수정되었습니다."
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 수정 실패: {str(e)}")


@router.delete("/orders/{order_id}", summary="주문 취소")
async def cancel_order(
    order_id: str,
    cancel_data: Optional[OrderCancel] = None,
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    주문을 취소합니다.
    - 대기중이거나 부분체결된 주문만 취소 가능
    """
    try:
        cancel_reason = cancel_data.cancel_reason if cancel_data else None
        cancelled_order = order_service.cancel_order(current_user_id, order_id, cancel_reason)
        order_response = OrderResponse.model_validate(cancelled_order)
        
        return create_response(
            data=order_response.model_dump(),
            message="주문이 성공적으로 취소되었습니다."
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 취소 실패: {str(e)}")

# @router.post("/orders/{order_id}/execute", summary="주문 강제 체결")
# async def execute_order(
#     order_id: str,
#     execution_price: Optional[float] = Query(None, description="체결가 (시장가일 경우)"),
#     current_user_id: str = Depends(get_current_user),
#     order_service: OrderService = Depends(get_order_service)
# ):
#     """
#     주문을 강제로 체결합니다. (관리자 전용 또는 시뮬레이션용)
#     """
#     try:
#         price = Decimal(str(execution_price)) if execution_price else None
#         executed_order = order_service.execute_order(current_user_id, order_id, price)
#         order_response = OrderResponse.model_validate(executed_order)
        
#         return create_response(
#             data=order_response.model_dump(),
#             message="주문이 성공적으로 체결되었습니다."
#         )
#     except NotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except ValidationError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"주문 체결 실패: {str(e)}")


# @router.post("/orders/{order_id}", summary="주문 체결 (주문가로 체결)")
# async def fill_order(
#     order_id: str,
#     current_user_id: str = Depends(get_current_user),
#     order_service: OrderService = Depends(get_order_service)
# ):
#     """간단 체결 API. 주문 가격으로 체결합니다."""
#     try:
#         # 주문 정보를 조회하여 주문가로 체결
#         order = order_service.get_order_by_id(current_user_id, order_id)
#         executed_order = order_service.execute_order(current_user_id, order_id, Decimal(order.order_price))
#         order_response = OrderResponse.model_validate(executed_order)
#         return create_response(
#             data=order_response.model_dump(),
#             message="주문이 성공적으로 체결되었습니다."
#         )
#     except NotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except ValidationError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"주문 체결 실패: {str(e)}")

