from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.config.db import get_db
from app.config.get_current_user import get_current_user
from app.config.di import get_transaction_service, get_portfolio_service
from app.services.transaction_service import TransactionService
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.trading_schema import (
    TransactionResponse, TransactionListResponse, TransactionSearchRequest,
    TradingStatisticsResponse, TradingPerformanceResponse, MonthlyPerformanceResponse,
    TradingDashboardResponse, MarketDataResponse, OrderBookResponse,
    TradingSignalResponse, RiskAssessmentResponse, BacktestRequest, BacktestResponse,
    TransactionTypeEnum
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


@router.get("/statistics", response_model=List[TradingStatisticsResponse], summary="거래 통계 조회")
async def get_trading_statistics(
    period_type: str = Query("monthly", description="기간 유형 (daily/weekly/monthly/yearly)"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """기간별 거래 통계를 조회합니다."""
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
        
        statistics = transaction_service.get_trading_statistics(
            user_id=current_user_id,
            period_type=period_type,
            start_date=parsed_start_date,
            end_date=parsed_end_date
        )
        
        return create_response(statistics, message="거래 통계 조회 성공")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 통계 조회 실패: {str(e)}")


@router.get("/performance", response_model=TradingPerformanceResponse, summary="거래 성과 분석")
async def get_trading_performance(
    period: str = Query("1Y", description="분석 기간 (1M/3M/6M/1Y/ALL)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    거래 성과를 분석합니다.
    - 총 수익률
    - 연환산 수익률
    - 변동성 및 샤프 비율
    - 최대 낙폭
    - 승률 및 수익 팩터
    """
    try:
        performance_data = transaction_service.get_trading_performance(current_user_id, period)
        
        performance = TradingPerformanceResponse(
            period=performance_data['period'],
            total_return=performance_data['total_return'],
            annualized_return=performance_data['annualized_return'],
            volatility=performance_data['volatility'],
            sharpe_ratio=performance_data['sharpe_ratio'],
            max_drawdown=performance_data['max_drawdown'],
            win_rate=performance_data['win_rate'],
            profit_factor=performance_data['profit_factor'],
            average_win=performance_data['average_win'],
            average_loss=performance_data['average_loss']
        )
        return create_response(performance.model_dump(), message="거래 성과 분석 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 성과 분석 실패: {str(e)}")


@router.get("/performance/monthly", response_model=List[MonthlyPerformanceResponse], summary="월별 성과")
async def get_monthly_performance(
    year: Optional[int] = Query(None, description="연도"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """월별 거래 성과를 조회합니다."""
    try:
        if year is None:
            year = datetime.now().year
        
        monthly_data = transaction_service.transaction_repo.get_monthly_summary(current_user_id, year)
        
        monthly_performance = []
        for data in monthly_data:
            performance = MonthlyPerformanceResponse(
                year=data['year'],
                month=data['month'],
                total_return=data['net_amount'],
                transaction_count=data['transaction_count'],
                buy_amount=data['buy_amount'],
                sell_amount=data['sell_amount'],
                profit_loss=data['net_amount'],
                profit_loss_rate=(data['net_amount'] / data['buy_amount'] * 100) if data['buy_amount'] > 0 else 0
            )
            monthly_performance.append(performance)
        
        return create_response([p.model_dump() for p in monthly_performance], message="월별 성과 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"월별 성과 조회 실패: {str(e)}")


@router.get("/dashboard", response_model=TradingDashboardResponse, summary="거래 대시보드")
async def get_trading_dashboard(
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    거래 대시보드 데이터를 조회합니다.
    - 계좌 요약
    - 최근 거래내역
    - 포트폴리오 요약
    - 성과 지표
    - 상위 수익/손실 종목
    """
    try:
        dashboard_data = transaction_service.get_trading_dashboard(current_user_id)
        
        performance_metrics_data = dashboard_data['performance_metrics']
        performance_metrics = TradingPerformanceResponse(
            period=performance_metrics_data['period'],
            total_return=performance_metrics_data['total_return'],
            annualized_return=performance_metrics_data['annualized_return'],
            volatility=performance_metrics_data['volatility'],
            sharpe_ratio=performance_metrics_data['sharpe_ratio'],
            max_drawdown=performance_metrics_data['max_drawdown'],
            win_rate=performance_metrics_data['win_rate'],
            profit_factor=performance_metrics_data['profit_factor'],
            average_win=performance_metrics_data['average_win'],
            average_loss=performance_metrics_data['average_loss']
        )
        
        dashboard = TradingDashboardResponse(
            account_summary=dashboard_data['account_summary'],
            recent_transactions=dashboard_data['recent_transactions'],
            portfolio_summary=dashboard_data['portfolio_summary'],
            performance_metrics=performance_metrics,
            monthly_performance=dashboard_data['monthly_performance'],
            top_gainers=dashboard_data['top_gainers'],
            top_losers=dashboard_data['top_losers']
        )
        return create_response(dashboard.model_dump(), message="거래 대시보드 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 대시보드 조회 실패: {str(e)}")


@router.get("/risk-assessment", response_model=RiskAssessmentResponse, summary="리스크 평가")
async def get_risk_assessment(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    포트폴리오의 리스크를 평가합니다.
    - 포트폴리오 리스크 점수
    - 집중도 리스크
    - 섹터별 노출도
    - 변동성 및 유동성 리스크
    """
    try:
        # 포트폴리오 대시보드 정보 조회
        portfolio_dashboard = portfolio_service.get_portfolio_dashboard(current_user_id)
        portfolios = portfolio_service.portfolio_repo.get_by_user_id(current_user_id, only_active=True)
        
        total_value = portfolio_dashboard['total_current_value']
        
        # 집중도 리스크 계산 (최대 보유 종목 비율)
        max_position_ratio = 0
        if portfolios and total_value > 0:
            max_value = max(float(p.current_quantity * p.average_price) for p in portfolios)
            max_position_ratio = (max_value / total_value) * 100
        
        # 집중도 리스크 점수 (0-100, 높을수록 위험)
        if max_position_ratio > 50:
            concentration_risk = 90
        elif max_position_ratio > 30:
            concentration_risk = 70
        elif max_position_ratio > 20:
            concentration_risk = 50
        elif max_position_ratio > 10:
            concentration_risk = 30
        else:
            concentration_risk = 10
        
        # 섹터별 노출도 (임시 데이터)
        sector_exposure = {
            "반도체": 35.5,
            "자동차": 20.3,
            "금융": 15.2,
            "바이오": 12.8,
            "화학": 8.7,
            "기타": 7.5
        }
        
        # 변동성 리스크 (임시 계산)
        volatility_risk = 65  # 임시 값 (실제로는 베타, 표준편차 등 계산)
        
        # 유동성 리스크 (임시 계산)
        liquidity_risk = 25  # 임시 값 (실제로는 일평균 거래량 등 고려)
        
        # 전체 포트폴리오 리스크 점수 (1-10점)
        portfolio_risk_score = round(
            (concentration_risk * 0.3 + volatility_risk * 0.4 + liquidity_risk * 0.3) / 10, 1
        )
        
        # 리스크 기반 추천사항
        recommendations = []
        
        if concentration_risk > 70:
            recommendations.append("특정 종목 집중도가 높습니다. 분산투자를 고려해보세요.")
        
        if volatility_risk > 70:
            recommendations.append("포트폴리오 변동성이 높습니다. 안정적인 종목 비중을 늘려보세요.")
        
        if liquidity_risk > 50:
            recommendations.append("일부 종목의 유동성이 낮습니다. 거래량이 충분한 종목을 고려해보세요.")
        
        if len(portfolios) < 5:
            recommendations.append("포트폴리오가 충분히 분산되지 않았습니다. 더 많은 종목으로 분산해보세요.")
        
        if sector_exposure.get("반도체", 0) > 40:
            recommendations.append("반도체 섹터 비중이 높습니다. 다른 섹터로의 분산을 고려해보세요.")
        
        if not recommendations:
            recommendations.append("현재 포트폴리오의 리스크 수준이 적절합니다.")
        
        risk_assessment = RiskAssessmentResponse(
            portfolio_risk_score=portfolio_risk_score,
            concentration_risk=concentration_risk,
            sector_exposure=sector_exposure,
            volatility_risk=volatility_risk,
            liquidity_risk=liquidity_risk,
            max_position_ratio=max_position_ratio,
            diversification_score=max(0, 100 - concentration_risk),
            total_positions=len(portfolios),
            recommendations=recommendations
        )
        return create_response(risk_assessment.model_dump(), message="리스크 평가 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리스크 평가 실패: {str(e)}")

