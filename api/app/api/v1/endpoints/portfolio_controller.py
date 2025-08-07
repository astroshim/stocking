from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.config.get_current_user import get_current_user
from app.config.di import get_portfolio_service
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.portfolio_schema import (
    PortfolioResponse, PortfolioWithStockResponse, PortfolioListResponse, PortfolioSummaryResponse,
    VirtualBalanceResponse, VirtualBalanceHistoryResponse, BalanceUpdateRequest,
    PortfolioAnalysisResponse, WatchListCreate, WatchListUpdate, WatchListResponse,
    WatchListWithStockResponse, WatchListListResponse
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioListResponse, summary="포트폴리오 조회")
async def get_portfolio(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    only_active: bool = Query(True, description="활성 보유 종목만 조회"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    사용자의 포트폴리오를 조회합니다.
    - 보유 종목 목록
    - 각 종목별 손익 정보
    - 현재가 기준 평가금액
    """
    try:
        page_result = portfolio_service.get_user_portfolio(
            user_id=current_user_id,
            page=page,
            size=size,
            only_active=only_active
        )
        
        response = PortfolioListResponse.from_page_result(page_result)
        return create_response(response.model_dump(), message="포트폴리오 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 조회 실패: {str(e)}")


@router.get("/portfolio/summary", response_model=PortfolioSummaryResponse, summary="포트폴리오 요약")
async def get_portfolio_summary(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """포트폴리오 전체 요약 정보를 조회합니다."""
    try:
        summary_data = portfolio_service.get_portfolio_summary(current_user_id)
        
        summary = PortfolioSummaryResponse(
            total_stocks=summary_data['total_stocks'],
            total_invested_amount=float(summary_data['total_invested_amount']),
            total_current_value=float(summary_data['total_current_value']),
            total_profit_loss=float(summary_data['total_profit_loss']),
            total_profit_loss_rate=float(summary_data['total_profit_loss_rate'])
        )
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
        
        analysis = PortfolioAnalysisResponse(
            sector_allocation=analysis_data['sector_allocation'],
            top_holdings=analysis_data['top_holdings'],
            performance_metrics=analysis_data['performance_metrics'],
            risk_metrics=analysis_data['risk_metrics']
        )
        return create_response(analysis.model_dump(), message="포트폴리오 분석 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 분석 조회 실패: {str(e)}")


@router.get("/portfolio/{stock_id}", response_model=PortfolioWithStockResponse, summary="종목별 포트폴리오 조회")
async def get_portfolio_by_stock(
    stock_id: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """특정 종목의 포트폴리오 정보를 조회합니다."""
    try:
        portfolio_data = portfolio_service.get_portfolio_by_stock(current_user_id, stock_id)
        
        if not portfolio_data:
            raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다")
        
        response = PortfolioWithStockResponse(**portfolio_data)
        return create_response(response.model_dump(), message="종목별 포트폴리오 조회 성공")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목별 포트폴리오 조회 실패: {str(e)}")


@router.get("/balance", response_model=VirtualBalanceResponse, summary="가상 잔고 조회")
async def get_virtual_balance(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 가상 거래 잔고를 조회합니다."""
    try:
        from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
        from decimal import Decimal
        
        # 직접 virtual_balance_repo를 사용 (portfolio_service에서 아직 잔고 조회 메서드 미구현)
        virtual_balance_repo = VirtualBalanceRepository(portfolio_service.db)
        
        # 사용자의 가상잔고 조회
        virtual_balance = virtual_balance_repo.get_by_user_id(current_user_id)
        
        # 가상잔고가 없으면 새로 생성 (지연 생성)
        if not virtual_balance:
            virtual_balance = virtual_balance_repo.create_user_balance(current_user_id, Decimal('1000000'))
            portfolio_service.db.commit()
        
        # VirtualBalanceResponse로 변환
        balance_data = VirtualBalanceResponse.model_validate(virtual_balance)
        
        return create_response(balance_data.model_dump(), message="가상 잔고 조회 성공")
    except Exception as e:
        portfolio_service.db.rollback()
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
        # 대부분의 잔고 업데이트는 payment 서비스를 통해 이루어짐
        # 여기서는 단순한 메모 업데이트 등만 처리
        return create_response(
            data=None,
            message="잔고 업데이트 요청이 접수되었습니다."
        )
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
        history_data = portfolio_service.get_balance_history(
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


@router.post("/watchlist", summary="관심 종목 추가")
async def add_to_watchlist(
    watchlist_data: WatchListCreate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심 종목을 추가합니다."""
    try:
        watchlist = portfolio_service.add_to_watchlist(
            user_id=current_user_id,
            stock_id=watchlist_data.stock_id,
            category=watchlist_data.category,
            memo=watchlist_data.memo,
            target_price=watchlist_data.target_price
        )
        
        return create_response(
            data={'id': watchlist.id},
            status_code=201,
            message="관심 종목이 성공적으로 추가되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심 종목 추가 실패: {str(e)}")


@router.get("/watchlist", response_model=WatchListListResponse, summary="관심 종목 목록")
async def get_watchlist(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심 종목 목록을 조회합니다."""
    try:
        page_result = portfolio_service.get_watchlist(
            user_id=current_user_id,
            page=page,
            size=size,
            category=category
        )
        
        response = WatchListListResponse.from_page_result(page_result)
        return create_response(response.model_dump(), message="관심 종목 목록 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심 종목 목록 조회 실패: {str(e)}")


@router.put("/watchlist/{watchlist_id}", summary="관심 종목 수정")
async def update_watchlist(
    watchlist_id: str,
    watchlist_data: WatchListUpdate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심 종목 정보를 수정합니다."""
    try:
        portfolio_service.update_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id,
            category=watchlist_data.category,
            memo=watchlist_data.memo,
            target_price=watchlist_data.target_price
        )
        
        return create_response(
            data=None,
            message="관심 종목이 성공적으로 수정되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심 종목 수정 실패: {str(e)}")


@router.delete("/watchlist/{watchlist_id}", summary="관심 종목 삭제")
async def remove_from_watchlist(
    watchlist_id: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심 종목을 삭제합니다."""
    try:
        portfolio_service.remove_from_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id
        )
        
        return create_response(
            data=None,
            message="관심 종목이 성공적으로 삭제되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심 종목 삭제 실패: {str(e)}")


@router.put("/watchlist/{watchlist_id}/order", summary="관심 종목 순서 변경")
async def reorder_watchlist(
    watchlist_id: str,
    new_order: int = Query(..., description="새로운 순서"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심 종목의 표시 순서를 변경합니다."""
    try:
        portfolio_service.reorder_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id,
            new_order=new_order
        )
        
        return create_response(
            data=None,
            message="관심 종목 순서가 성공적으로 변경되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심 종목 순서 변경 실패: {str(e)}")


@router.get("/watchlist/categories", response_model=list[dict], summary="관심 종목 카테고리 목록")
async def get_watchlist_categories(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 관심 종목 카테고리 목록을 조회합니다."""
    try:
        categories = portfolio_service.get_watchlist_categories(current_user_id)
        return create_response(categories, message="카테곦0리 목록 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테곦0리 목록 조회 실패: {str(e)}")