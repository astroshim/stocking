from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.config.get_current_user import get_current_user
from app.config.di import get_portfolio_service
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.portfolio_schema import (
    PortfolioResponse, PortfolioWithStockResponse, PortfolioListResponse, PortfolioSummaryResponse,
    PortfolioAnalysisResponse, PortfolioDashboardResponse, InvestmentWeightResponse
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("", response_model=PortfolioListResponse, summary="포트폴리오 조회")
async def get_portfolio(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    only_active: bool = Query(True, description="활성 보유 종목만 조회"),
    include_orders: bool = Query(False, description="주문 정보 포함 여부"),
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
            only_active=only_active,
            include_orders=include_orders
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
            total_invested_amount_krw=float(summary_data['total_invested_amount_krw']) if summary_data.get('total_invested_amount_krw') is not None else None,
            total_current_value=float(summary_data['total_current_value']),
            total_current_value_krw=float(summary_data['total_current_value_krw']) if summary_data.get('total_current_value_krw') is not None else None,
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


@router.get("/dashboard", response_model=PortfolioDashboardResponse, summary="포트폴리오 대시보드")
async def get_portfolio_dashboard(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    포트폴리오 대시보드 정보를 조회합니다.
    
    포함되는 정보:
    - 현재 총 투자금액 (원금)
    - 현재 총 평가금액
    - 총 수익금 (평가금 - 원금)
    - 총 수익률 (%)
    - 일간 손익금 (각 종목의 일간 손익금의 합)
    - 일간 손익률 (%)
    
    * 해외 주식의 경우 현재 환율을 적용하여 계산합니다.
    """
    try:
        dashboard_data = portfolio_service.get_portfolio_dashboard(current_user_id)
        
        dashboard = PortfolioDashboardResponse(
            total_invested_amount=dashboard_data['total_invested_amount'],
            total_current_value=dashboard_data['total_current_value'],
            total_profit_loss=dashboard_data['total_profit_loss'],
            total_profit_loss_rate=dashboard_data['total_profit_loss_rate'],
            daily_profit_loss=dashboard_data['daily_profit_loss'],
            daily_profit_loss_rate=dashboard_data['daily_profit_loss_rate']
        )
        return create_response(dashboard.model_dump(), message="포트폴리오 대시보드 조회 성공")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"포트폴리오 대시보드 조회 실패: {str(e)}")


@router.get("/investment-weights", response_model=InvestmentWeightResponse, summary="투자 비중 조회")
async def get_investment_weights(
    filter_type: str = Query('total', description="필터 타입 (total/domestic/foreign/sector/sector_group)"),
    sector: Optional[str] = Query(None, description="섹터명 (filter_type이 'sector'일 때 필수)"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    투자 비중 정보를 조회합니다.
    
    필터 타입:
    - **total**: 전체 포트폴리오
    - **domestic**: 국내 주식만
    - **foreign**: 해외 주식만
    - **sector**: 특정 섹터별 (sector 파라미터 필수)
    - **sector_group**: 섹터별로 그룹화하여 표시
    
    응답 정보:
    - 총 투자금액 (KRW 기준)
    - 종목별 투자금액 및 투자 비중(%) - filter_type이 sector_group이 아닌 경우
    - 섹터별 투자금액 및 투자 비중(%) - filter_type이 sector_group인 경우
    - 투자 비중 기준 내림차순 정렬
    
    * 해외 주식의 경우 현재 환율을 적용하여 KRW로 환산합니다.
    """
    try:
        # filter_type 유효성 검사
        valid_filter_types = ['total', 'domestic', 'foreign', 'sector', 'sector_group']
        if filter_type not in valid_filter_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter_type. Must be one of: {', '.join(valid_filter_types)}"
            )
        
        # sector 필터일 때 sector 파라미터 필수
        if filter_type == 'sector' and not sector:
            raise HTTPException(
                status_code=400,
                detail="sector parameter is required when filter_type is 'sector'"
            )
        
        weight_data = portfolio_service.get_investment_weights(
            user_id=current_user_id,
            filter_type=filter_type,
            sector=sector
        )
        
        response = InvestmentWeightResponse(
            filter_type=weight_data['filter_type'],
            sector_name=weight_data.get('sector_name'),
            total_invested_amount=weight_data['total_invested_amount'],
            total_current_value=weight_data['total_current_value'],
            total_profit_loss=weight_data['total_profit_loss'],
            total_profit_loss_rate=weight_data['total_profit_loss_rate'],
            items=weight_data.get('items'),
            sector_items=weight_data.get('sector_items')
        )
        
        return create_response(response.model_dump(), message="투자 비중 조회 성공")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"투자 비중 조회 실패: {str(e)}")



