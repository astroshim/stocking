from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.config.get_current_user import get_current_user
from app.config.di import get_balance_service
from app.services.balance_service import BalanceService
from app.api.v1.schemas.virtual_balance_schema import (
    VirtualBalanceResponse, VirtualBalanceHistoryResponse, BalanceUpdateRequest
)
from app.utils.response_helper import create_response

router = APIRouter()


@router.get("/", response_model=VirtualBalanceResponse, summary="가상 잔고 조회")
async def get_virtual_balance(
    current_user_id: str = Depends(get_current_user),
    balance_service: BalanceService = Depends(get_balance_service)
):
    """사용자의 가상 거래 잔고를 조회합니다."""
    try:
        virtual_balance = balance_service.get_virtual_balance(current_user_id)
        
        # 가상잔고가 없으면 새로 생성 (지연 생성)
        if not virtual_balance:
            virtual_balance = balance_service.initialize_virtual_balance(current_user_id)
        
        # VirtualBalanceResponse로 변환
        balance_data = VirtualBalanceResponse.model_validate(virtual_balance)
        
        return create_response(balance_data.model_dump(), message="가상 잔고 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가상 잔고 조회 실패: {str(e)}")


@router.put("/", summary="가상 잔고 업데이트")
async def update_virtual_balance(
    balance_data: BalanceUpdateRequest,
    current_user_id: str = Depends(get_current_user),
    balance_service: BalanceService = Depends(get_balance_service)
):
    """
    가상 거래 잔고를 업데이트합니다.
    - 입금/출금 처리
    - 잔고 이력 기록
    """
    try:
        # 대부분의 잔고 업데이트는 payment 서비스를 통해 이루어짐
        # 여기서는 단순한 메모 업데이트 등만 처리
        result = balance_service.update_balance(current_user_id, balance_data)
        
        return create_response(
            data=result,
            message="잔고 업데이트가 완료되었습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 업데이트 실패: {str(e)}")


@router.get("/history", response_model=list[VirtualBalanceHistoryResponse], summary="잔고 변동 이력")
async def get_balance_history(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(50, ge=1, le=100, description="페이지 크기"),
    change_type: Optional[str] = Query(None, description="변경 유형 필터"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    balance_service: BalanceService = Depends(get_balance_service)
):
    """잔고 변동 이력을 조회합니다."""
    try:
        history_data = balance_service.get_balance_history(
            user_id=current_user_id,
            page=page,
            size=size,
            change_type=change_type,
            start_date=start_date,
            end_date=end_date
        )
        return create_response(history_data, message="잔고 변동 이력 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 이력 조회 실패: {str(e)}")


@router.post("/deposit", summary="가상 잔고 입금")
async def deposit_virtual_balance(
    amount: float = Query(..., description="입금 금액"),
    description: Optional[str] = Query(None, description="입금 설명"),
    current_user_id: str = Depends(get_current_user),
    balance_service: BalanceService = Depends(get_balance_service)
):
    """가상 거래 잔고에 입금합니다."""
    try:
        virtual_balance = balance_service.deposit(current_user_id, amount, description)
        
        balance_data = VirtualBalanceResponse.model_validate(virtual_balance)
        return create_response(balance_data.model_dump(), message="입금이 완료되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"입금 실패: {str(e)}")


@router.post("/withdraw", summary="가상 잔고 출금")
async def withdraw_virtual_balance(
    amount: float = Query(..., description="출금 금액"),
    description: Optional[str] = Query(None, description="출금 설명"),
    current_user_id: str = Depends(get_current_user),
    balance_service: BalanceService = Depends(get_balance_service)
):
    """가상 거래 잔고에서 출금합니다."""
    try:
        virtual_balance = balance_service.withdraw(current_user_id, amount, description)
        
        balance_data = VirtualBalanceResponse.model_validate(virtual_balance)
        return create_response(balance_data.model_dump(), message="출금이 완료되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"출금 실패: {str(e)}")
