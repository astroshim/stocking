from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.config.db import get_db
from app.config.get_current_user import get_current_user
from app.config.di import get_portfolio_service
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.portfolio_schema import (
    PortfolioResponse, PortfolioWithStockResponse, PortfolioListResponse, PortfolioSummaryResponse,
    VirtualBalanceResponse, VirtualBalanceHistoryResponse, BalanceUpdateRequest,
    PortfolioAnalysisResponse, WatchListCreate, WatchListUpdate, WatchListResponse,
    WatchListWithStockResponse, WatchListListResponse, BalanceChangeTypeEnum
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioListResponse, summary="포트폴리오 조회")
async def get_portfolio(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    only_active: bool = Query(True, description="활성 보유 종목만 조회"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    사용자의 포트폴리오를 조회합니다.
    - 보유 종목 목록
    - 각 종목별 손익 정보
    - 현재가 기준 평가금액
    """
    # TODO: 실제 포트폴리오 조회 로직 구현
    # 임시로 빈 페이지 결과 생성
    page_result = SimplePage(
        items=[],
        page=page,
        per_page=size,
        has_next=False
    )
    
    response = PortfolioListResponse.from_page_result(page_result)
    return create_response(response.model_dump(), message="포트폴리오 조회 성공")


@router.get("/portfolio/summary", response_model=PortfolioSummaryResponse, summary="포트폴리오 요약")
async def get_portfolio_summary(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """포트폴리오 전체 요약 정보를 조회합니다."""
    try:
        summary_data = portfolio_service.get_portfolio_summary(current_user_id)
        summary = PortfolioSummaryResponse(**summary_data)
        return create_response(summary.model_dump(), message="포트폴리오 요약 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 요약 조회 실패: {str(e)}")


@router.get("/portfolio/analysis", response_model=PortfolioAnalysisResponse, summary="포트폴리오 분석")
async def get_portfolio_analysis(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    포트폴리오 분석 결과를 조회합니다.
    - 섹터별 배분
    - 상위 보유 종목
    - 성과 지표
    - 리스크 지표
    """
    try:
        analysis_data = portfolio_service.get_portfolio_analysis(current_user_id)
        analysis = PortfolioAnalysisResponse(**analysis_data)
        return create_response(analysis.model_dump(), message="포트폴리오 분석 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 분석 조회 실패: {str(e)}")


@router.get("/portfolio/{stock_id}", response_model=PortfolioWithStockResponse, summary="종목별 포트폴리오 조회")
async def get_portfolio_by_stock(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """특정 종목의 포트폴리오 정보를 조회합니다."""
    # TODO: 실제 종목별 포트폴리오 조회 로직 구현
    raise HTTPException(status_code=404, detail="Portfolio not found")


@router.get("/balance", response_model=VirtualBalanceResponse, summary="가상 잔고 조회")
async def get_virtual_balance(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 가상 거래 잔고를 조회합니다."""
    try:
        virtual_balance = portfolio_service.get_virtual_balance(current_user_id)
        
        # VirtualBalanceResponse로 변환
        balance_data = VirtualBalanceResponse.model_validate(virtual_balance)
        
        return create_response(balance_data.model_dump(), message="가상 잔고 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가상 잔고 조회 실패: {str(e)}")


@router.put("/balance", summary="가상 잔고 업데이트")
async def update_virtual_balance(
    balance_data: BalanceUpdateRequest,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    가상 거래 잔고를 업데이트합니다.
    - 입금/출금 처리
    - 잔고 이력 기록
    """
    try:
        updated_balance = portfolio_service.update_virtual_balance(
            user_id=current_user_id,
            amount=balance_data.amount,
            change_type=balance_data.change_type,
            description=balance_data.description
        )
        
        # 업데이트된 잔고 정보 반환
        balance_response = VirtualBalanceResponse.model_validate(updated_balance)
        
        return create_response(
            data=balance_response.model_dump(),
            message=f"잔고가 성공적으로 업데이트되었습니다. ({balance_data.change_type}: {balance_data.amount}원)"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 업데이트 실패: {str(e)}")


@router.get("/balance/history", response_model=list[VirtualBalanceHistoryResponse], summary="잔고 변동 이력")
async def get_balance_history(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(50, ge=1, le=100, description="페이지 크기"),
    change_type: Optional[str] = Query(None, description="변경 유형 필터"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """잔고 변동 이력을 조회합니다."""
    try:
        history_records = portfolio_service.get_balance_history(
            user_id=current_user_id,
            page=page,
            size=size,
            change_type=change_type,
            start_date=start_date,
            end_date=end_date
        )
        
        # VirtualBalanceHistoryResponse로 변환
        history_responses = [
            VirtualBalanceHistoryResponse.model_validate(record) 
            for record in history_records
        ]
        
        return create_response(
            data=[response.model_dump() for response in history_responses], 
            message=f"잔고 변동 이력 조회 성공 ({len(history_responses)}건)"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 이력 조회 실패: {str(e)}")


@router.post("/watchlist", summary="관심 종목 추가")
async def add_to_watchlist(
    watchlist_data: WatchListCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """관심 종목을 추가합니다."""
    # TODO: 실제 관심 종목 추가 로직 구현
    return create_response(
        data=None,
        status_code=201,
        message="관심 종목이 성공적으로 추가되었습니다."
    )


@router.get("/watchlist", response_model=WatchListListResponse, summary="관심 종목 목록")
async def get_watchlist(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """관심 종목 목록을 조회합니다."""
    # TODO: 실제 관심 종목 목록 조회 로직 구현
    # 임시로 빈 페이지 결과 생성
    page_result = SimplePage(
        items=[],
        page=page,
        per_page=size,
        has_next=False
    )
    
    response = WatchListListResponse.from_page_result(page_result)
    return create_response(response.model_dump(), message="관심 종목 목록 조회 성공")


@router.put("/watchlist/{watchlist_id}", summary="관심 종목 수정")
async def update_watchlist(
    watchlist_id: str,
    watchlist_data: WatchListUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """관심 종목 정보를 수정합니다."""
    # TODO: 실제 관심 종목 수정 로직 구현
    return create_response(
        data=None,
        message="관심 종목이 성공적으로 수정되었습니다."
    )


@router.delete("/watchlist/{watchlist_id}", summary="관심 종목 삭제")
async def remove_from_watchlist(
    watchlist_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """관심 종목을 삭제합니다."""
    # TODO: 실제 관심 종목 삭제 로직 구현
    return create_response(
        data=None,
        message="관심 종목이 성공적으로 삭제되었습니다."
    )


@router.put("/watchlist/{watchlist_id}/order", summary="관심 종목 순서 변경")
async def reorder_watchlist(
    watchlist_id: str,
    new_order: int = Query(..., description="새로운 순서"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """관심 종목의 표시 순서를 변경합니다."""
    # TODO: 실제 순서 변경 로직 구현
    return create_response(
        data=None,
        message="관심 종목 순서가 성공적으로 변경되었습니다."
    )


@router.get("/watchlist/categories", response_model=list[dict], summary="관심 종목 카테고리 목록")
async def get_watchlist_categories(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """사용자의 관심 종목 카테고리 목록을 조회합니다."""
    # TODO: 실제 카테고리 목록 조회 로직 구현
    categories = [
        {"name": "기본", "count": 0},
        {"name": "관심주", "count": 0},
        {"name": "배당주", "count": 0},
        {"name": "성장주", "count": 0}
    ]
    return create_response(categories, message="카테고리 목록 조회 성공")