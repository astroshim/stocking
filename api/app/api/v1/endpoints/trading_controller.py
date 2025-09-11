from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import Optional

from app.config.get_current_user import get_current_user
from app.config.di import get_transaction_service, get_portfolio_service
from app.services.transaction_service import TransactionService
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.trading_schema import (
    TransactionResponse, TransactionListResponse, TransactionSearchRequest,
    TransactionTypeEnum, PeriodRealizedProfitLossResponse, StockRealizedProfitLossResponse
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("/transactions", response_model=TransactionListResponse, summary="거래 내역 조회")
async def get_transactions(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    transaction_type: Optional[TransactionTypeEnum] = Query(None, description="거래 유형"),
    stock_id: Optional[str] = Query(None, description="주식 종목 ID"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    사용자의 거래 내역을 조회합니다.
    - 매수/매도 거래
    - 입출금 내역
    - 배당금 수령 내역
    - 수수료 및 세금 내역
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
        
        # TransactionType 변환
        from app.db.models.transaction import TransactionType
        transaction_type_filter = None
        if transaction_type:
            try:
                transaction_type_filter = TransactionType(transaction_type.value)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid transaction type")
        
        page_result = transaction_service.get_transactions(
            user_id=current_user_id,
            page=page,
            size=size,
            transaction_type=transaction_type_filter,
            stock_id=stock_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date
        )
        
        response = TransactionListResponse.from_page_result(page_result)
        return create_response(response.model_dump(), message="거래 내역 조회 성공")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 내역 조회 실패: {str(e)}")


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse, summary="거래 내역 상세")
async def get_transaction(
    transaction_id: str,
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """특정 거래의 상세 내역을 조회합니다."""
    try:
        transaction_data = transaction_service.get_transaction_by_id(current_user_id, transaction_id)
        
        if not transaction_data:
            raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다")
        
        response = TransactionResponse(**transaction_data)
        return create_response(response.model_dump(), message="거래 내역 상세 조회 성공")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 내역 상세 조회 실패: {str(e)}")


@router.get("/realized-profit-loss/period", response_model=PeriodRealizedProfitLossResponse, summary="기간별 실현 손익 조회 (일별 상세)")
async def get_period_realized_profit_loss(
    period_type: str = Query(..., description="기간 타입 (day/week/month/year/all)"),
    period_value: Optional[str] = Query(None, description="기간 값 (예: 2024-09-10, 2024-10-2, 2024-09, 2024)"),
    stock_type: str = Query("total", description="주식 유형 (domestic/foreign/total)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    특정 기간의 실현 손익을 일별로 상세하게 조회합니다.
    
    **기간 타입별 형식**:
    - `day`: 특정 날짜 (예: period_value=2024-09-10)
    - `week`: 특정 주 (예: period_value=2024-10-2 => 2024년 10월 2주)
    - `month`: 특정 월 (예: period_value=2024-09)
    - `year`: 특정 년도 (예: period_value=2024)
    - `all`: 전체 기간 (period_value 불필요)
    
    **주식 유형별 필터**:
    - `domestic`: 국내주식만 (A로 시작하는 종목)
    - `foreign`: 해외주식만 (US, NAS로 시작하는 종목)
    - `total`: 전체 (기본값)
    
    **응답 데이터**:
    - 지정 기간의 총 실현 손익
    - 일별 상세 데이터 (각 날짜별 거래 종목 포함)
    
    매도 거래에서 발생한 실현 손익만 집계됩니다.
    """
    try:
        # period_type 유효성 검증
        valid_types = ['day', 'week', 'month', 'year', 'all']
        if period_type not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period_type. Use one of: {', '.join(valid_types)}"
            )
        
        # stock_type 유효성 검증
        valid_stock_types = ['domestic', 'foreign', 'total']
        if stock_type not in valid_stock_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid stock_type. Use one of: {', '.join(valid_stock_types)}"
            )
        
        # 실현 손익 데이터 조회
        period_data = transaction_service.get_period_realized_profit_loss(
            user_id=current_user_id,
            period_type=period_type,
            period_value=period_value,
            stock_type=stock_type
        )
        
        # 응답 스키마로 변환
        response = PeriodRealizedProfitLossResponse(**period_data)
        return create_response(response.model_dump(), message="기간별 실현 손익 조회 성공")
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"기간별 실현 손익 조회 실패: {str(e)}")


@router.get("/realized-profit-loss/stocks", response_model=StockRealizedProfitLossResponse, summary="종목별 실현 손익 조회")
async def get_stock_realized_profit_loss(
    period_type: str = Query(..., description="기간 타입 (day/week/month/year/all)"),
    period_value: Optional[str] = Query(None, description="기간 값 (예: 2024-09-10, 2024-10-2, 2024-09, 2024)"),
    stock_type: str = Query("total", description="주식 유형 (domestic/foreign/total)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    특정 기간의 종목별 실현 손익을 조회합니다.
    
    **기간 타입별 형식**:
    - `day`: 특정 날짜 (예: period_value=2024-09-10)
    - `week`: 특정 주 (예: period_value=2024-10-2 => 2024년 10월 2주)
    - `month`: 특정 월 (예: period_value=2024-09)
    - `year`: 특정 년도 (예: period_value=2024)
    - `all`: 전체 기간 (period_value 불필요)
    
    **주식 유형별 필터**:
    - `domestic`: 국내주식만 (A로 시작하는 종목)
    - `foreign`: 해외주식만 (US, NAS로 시작하는 종목)
    - `total`: 전체 (기본값)
    
    **응답 데이터**:
    - 지정 기간의 총 실현 손익
    - 종목별 상세 데이터 (수익률 순 정렬)
    - 각 종목의 첫 거래일과 마지막 거래일
    
    매도 거래에서 발생한 실현 손익만 집계됩니다.
    """
    try:
        # period_type 유효성 검증
        valid_types = ['day', 'week', 'month', 'year', 'all']
        if period_type not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid period_type. Use one of: {', '.join(valid_types)}"
            )
        
        # stock_type 유효성 검증
        valid_stock_types = ['domestic', 'foreign', 'total']
        if stock_type not in valid_stock_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid stock_type. Use one of: {', '.join(valid_stock_types)}"
            )
        
        # 실현 손익 데이터 조회
        stock_data = transaction_service.get_stock_realized_profit_loss(
            user_id=current_user_id,
            period_type=period_type,
            period_value=period_value,
            stock_type=stock_type
        )
        
        # 응답 스키마로 변환
        response = StockRealizedProfitLossResponse(**stock_data)
        return create_response(response.model_dump(), message="종목별 실현 손익 조회 성공")
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목별 실현 손익 조회 실패: {str(e)}")

