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
    OrderListResponse, OrderSearchRequest, OrderSummaryResponse, QuickOrderRequest,
    OrderStatusEnum, OrderTypeEnum
)
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
        order = order_service.create_order(current_user_id, order_data.model_dump())
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


@router.post("/orders/quick", summary="빠른 주문")
async def create_quick_order(
    quick_order: QuickOrderRequest,
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    빠른 주문 (시장가 즉시 체결)
    - 매수: 금액 기준으로 주문
    - 매도: 수량 기준으로 주문
    """
    try:
        order = order_service.create_quick_order(
            current_user_id,
            quick_order.stock_id,
            quick_order.order_type,
            quick_order.amount_or_quantity
        )
        order_response = OrderResponse.model_validate(order)
        
        return create_response(
            data=order_response.model_dump(),
            status_code=201,
            message="빠른 주문이 성공적으로 처리되었습니다."
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"빠른 주문 처리 실패: {str(e)}")


@router.get("/orders", response_model=OrderListResponse, summary="주문 목록 조회")
async def get_orders(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    status: Optional[OrderStatusEnum] = Query(None, description="주문 상태"),
    order_type: Optional[OrderTypeEnum] = Query(None, description="주문 유형"),
    stock_id: Optional[str] = Query(None, description="주식 종목 ID"),
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """사용자의 주문 목록을 조회합니다."""
    try:
        result = order_service.get_orders(current_user_id, page, size, status, order_type, stock_id)
        
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
        return create_response(paged_response.model_dump(), message="주문 목록 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 목록 조회 실패: {str(e)}")


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


@router.post("/orders/{order_id}/execute", summary="주문 강제 체결")
async def execute_order(
    order_id: str,
    execution_price: Optional[float] = Query(None, description="체결가 (시장가일 경우)"),
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """
    주문을 강제로 체결합니다. (관리자 전용 또는 시뮬레이션용)
    """
    try:
        price = Decimal(str(execution_price)) if execution_price else None
        executed_order = order_service.execute_order(current_user_id, order_id, price)
        order_response = OrderResponse.model_validate(executed_order)
        
        return create_response(
            data=order_response.model_dump(),
            message="주문이 성공적으로 체결되었습니다."
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 체결 실패: {str(e)}")


@router.get("/orders/history", response_model=OrderListResponse, summary="주문 이력 조회")
async def get_order_history(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service)
):
    """주문 이력을 조회합니다 (체결완료, 취소된 주문 포함)."""
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
        
        result = order_service.get_order_history(current_user_id, page, size, parsed_start_date, parsed_end_date)
        
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
        return create_response(paged_response.model_dump(), message="주문 이력 조회 성공")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주문 이력 조회 실패: {str(e)}")