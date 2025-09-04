from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.config.get_current_user import get_current_user
from app.config.di import get_portfolio_service
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.portfolio_schema import (
    PortfolioResponse, PortfolioWithStockResponse, PortfolioListResponse, PortfolioSummaryResponse,
    PortfolioAnalysisResponse
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("/", response_model=PortfolioListResponse, summary="포트폴리오 조회")
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


@router.get("/summary", response_model=PortfolioSummaryResponse, summary="포트폴리오 요약")
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


@router.get("/analysis", response_model=PortfolioAnalysisResponse, summary="포트폴리오 분석")
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


@router.get("/product/{product_code}", response_model=PortfolioWithStockResponse, summary="종목별 포트폴리오 조회")
async def get_portfolio_by_stock(
    product_code: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """특정 종목의 포트폴리오 정보를 조회합니다."""
    try:
        portfolio_data = portfolio_service.get_portfolio_by_stock(current_user_id, product_code)
        
        if not portfolio_data:
            raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다")
        
        response = PortfolioWithStockResponse(**portfolio_data)
        return create_response(response.model_dump(), message="종목별 포트폴리오 조회 성공")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목별 포트폴리오 조회 실패: {str(e)}")



