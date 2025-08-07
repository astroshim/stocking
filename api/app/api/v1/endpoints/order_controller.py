from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.config.db import get_db
from app.config.get_current_user import get_current_user
from app.api.v1.schemas.order_schema import (
    OrderCreate, OrderUpdate, OrderCancel, OrderResponse, OrderWithExecutionsResponse,
    OrderListResponse, OrderSearchRequest, OrderSummaryResponse, QuickOrderRequest,
    OrderStatusEnum, OrderTypeEnum
)
from app.utils.response_helper import create_response

router = APIRouter()


@router.post("/orders", summary="주문 생성")
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    새로운 주문을 생성합니다.
    - 매수/매도 주문 지원
    - 시장가/지정가 주문 지원
    - 손절매/이익실현 주문 지원
    """
    # TODO: 실제 주문 생성 로직 구현
    # 1. 주문 유효성 검증
    # 2. 잔고 확인 (매수시)
    # 3. 보유 수량 확인 (매도시)
    # 4. 주문 생성 및 체결 처리
    return create_response(
        data=None,
        status_code=201,
        message="주문이 성공적으로 생성되었습니다."
    )


@router.post("/orders/quick", summary="빠른 주문")
async def create_quick_order(
    quick_order: QuickOrderRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    빠른 주문 (시장가 즉시 체결)
    - 매수: 금액 기준으로 주문
    - 매도: 수량 기준으로 주문
    """
    # TODO: 빠른 주문 로직 구현
    return create_response(
        data=None,
        status_code=201,
        message="빠른 주문이 성공적으로 처리되었습니다."
    )


@router.get("/orders", response_model=OrderListResponse, summary="주문 목록 조회")
async def get_orders(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    status: Optional[OrderStatusEnum] = Query(None, description="주문 상태"),
    order_type: Optional[OrderTypeEnum] = Query(None, description="주문 유형"),
    stock_id: Optional[str] = Query(None, description="주식 종목 ID"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """사용자의 주문 목록을 조회합니다."""
    # TODO: 실제 주문 목록 조회 로직 구현
    return OrderListResponse(
        items=[],
        total=0,
        page=page,
        size=size,
        pages=0
    )


@router.get("/orders/{order_id}", response_model=OrderWithExecutionsResponse, summary="주문 상세 조회")
async def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """특정 주문의 상세 정보와 체결 내역을 조회합니다."""
    # TODO: 실제 주문 상세 조회 로직 구현
    raise HTTPException(status_code=404, detail="Order not found")


@router.put("/orders/{order_id}", summary="주문 수정")
async def update_order(
    order_id: str,
    order_data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    주문을 수정합니다.
    - 대기중인 주문만 수정 가능
    - 가격, 수량, 만료일 수정 가능
    """
    # TODO: 실제 주문 수정 로직 구현
    return create_response(
        data=None,
        message="주문이 성공적으로 수정되었습니다."
    )


@router.delete("/orders/{order_id}", summary="주문 취소")
async def cancel_order(
    order_id: str,
    cancel_data: Optional[OrderCancel] = None,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    주문을 취소합니다.
    - 대기중이거나 부분체결된 주문만 취소 가능
    """
    # TODO: 실제 주문 취소 로직 구현
    return create_response(
        data=None,
        message="주문이 성공적으로 취소되었습니다."
    )


@router.get("/orders/summary", response_model=OrderSummaryResponse, summary="주문 요약 정보")
async def get_order_summary(
    period_days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """지정된 기간의 주문 요약 정보를 조회합니다."""
    # TODO: 실제 주문 요약 정보 조회 로직 구현
    return OrderSummaryResponse(
        total_orders=0,
        pending_orders=0,
        filled_orders=0,
        cancelled_orders=0,
        total_buy_amount=0,
        total_sell_amount=0,
        total_commission=0
    )


@router.get("/orders/pending", response_model=OrderListResponse, summary="대기중인 주문 조회")
async def get_pending_orders(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """현재 대기중인 주문들을 조회합니다."""
    # TODO: 실제 대기중인 주문 조회 로직 구현
    return OrderListResponse(
        items=[],
        total=0,
        page=page,
        size=size,
        pages=0
    )


@router.post("/orders/{order_id}/execute", summary="주문 강제 체결")
async def execute_order(
    order_id: str,
    execution_price: Optional[float] = Query(None, description="체결가 (시장가일 경우)"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    주문을 강제로 체결합니다. (관리자 전용 또는 시뮬레이션용)
    """
    # TODO: 권한 체크 및 강제 체결 로직 구현
    return create_response(
        data=None,
        message="주문이 성공적으로 체결되었습니다."
    )


@router.get("/orders/history", response_model=OrderListResponse, summary="주문 이력 조회")
async def get_order_history(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주문 이력을 조회합니다 (체결완료, 취소된 주문 포함)."""
    # TODO: 실제 주문 이력 조회 로직 구현
    return OrderListResponse(
        items=[],
        total=0,
        page=page,
        size=size,
        pages=0
    )