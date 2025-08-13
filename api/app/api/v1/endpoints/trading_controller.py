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


@router.get("/market-data", response_model=MarketDataResponse, summary="시장 데이터")
async def get_market_data(
    current_user_id: str = Depends(get_current_user)
):
    """
    시장 데이터를 조회합니다.
    - 주요 지수
    - 시장 뉴스
    - 인기 종목
    - 섹터별 성과
    """
    try:
        # 임시 시장 데이터 (실제로는 toss API 연동)
        market_indices = [
            {"name": "KOSPI", "value": 2580.50, "change": 15.30, "change_rate": 0.60},
            {"name": "KOSDAQ", "value": 850.20, "change": -8.50, "change_rate": -0.99},
            {"name": "KRX 100", "value": 5420.80, "change": 25.60, "change_rate": 0.47}
        ]
        
        market_news = [
            {
                "title": "반도체 업종 강세 지속, 수출 증가 기대감",
                "summary": "메모리 반도체 가격 상승으로 관련 종목들이 강세를 보이고 있습니다.",
                "published_at": datetime.now().isoformat(),
                "source": "경제신문"
            },
            {
                "title": "금리 인하 기대감으로 은행주 상승",
                "summary": "중앙은행의 금리 인하 가능성이 높아지면서 은행 관련 주식이 상승세를 보입니다.",
                "published_at": datetime.now().isoformat(),
                "source": "금융뉴스"
            }
        ]
        
        trending_stocks = [
            {"stock_id": "005930", "name": "삼성전자", "price": 75000, "change_rate": 2.5, "volume": 15000000},
            {"stock_id": "000660", "name": "SK하이닉스", "price": 128000, "change_rate": 3.2, "volume": 8500000},
            {"stock_id": "035420", "name": "NAVER", "price": 185000, "change_rate": -1.8, "volume": 2100000}
        ]
        
        sector_performance = [
            {"sector": "반도체", "change_rate": 2.8, "market_cap": 450000000000},
            {"sector": "자동차", "change_rate": -0.5, "market_cap": 120000000000},
            {"sector": "바이오", "change_rate": 1.2, "market_cap": 85000000000},
            {"sector": "금융", "change_rate": 0.8, "market_cap": 180000000000}
        ]
        
        market_data = MarketDataResponse(
            market_indices=market_indices,
            market_news=market_news,
            trending_stocks=trending_stocks,
            sector_performance=sector_performance
        )
        return create_response(market_data.model_dump(), message="시장 데이터 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시장 데이터 조회 실패: {str(e)}")


@router.get("/orderbook/{stock_id}", response_model=OrderBookResponse, summary="호가창 조회")
async def get_orderbook(
    stock_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """특정 종목의 호가창 정보를 조회합니다."""
    try:
        # 임시 호가창 데이터 (실제로는 실시간 API 연동)
        current_price = 75000  # 현재가 (임시)
        
        # 매수 호가 (현재가보다 낮은 가격)
        bid_orders = []
        for i in range(10):
            price = current_price - (i + 1) * 100
            quantity = (i + 1) * 1000 + (i * 500)
            bid_orders.append({
                "price": price,
                "quantity": quantity,
                "order_count": i + 5
            })
        
        # 매도 호가 (현재가보다 높은 가격)
        ask_orders = []
        for i in range(10):
            price = current_price + (i + 1) * 100
            quantity = (i + 1) * 800 + (i * 300)
            ask_orders.append({
                "price": price,
                "quantity": quantity,
                "order_count": i + 3
            })
        
        orderbook = OrderBookResponse(
            stock_id=stock_id,
            timestamp=datetime.now(),
            current_price=current_price,
            bid_orders=bid_orders,
            ask_orders=ask_orders,
            total_bid_quantity=sum(order["quantity"] for order in bid_orders),
            total_ask_quantity=sum(order["quantity"] for order in ask_orders),
            spread=ask_orders[0]["price"] - bid_orders[0]["price"] if bid_orders and ask_orders else 0
        )
        return create_response(orderbook.model_dump(), message="호가창 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"호가창 조회 실패: {str(e)}")


@router.get("/signals/{stock_id}", response_model=TradingSignalResponse, summary="매매 신호")
async def get_trading_signal(
    stock_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """특정 종목의 매매 신호를 조회합니다."""
    try:
        # 임시 매매 신호 분석 로직 (실제로는 AI/알고리즘 분석)
        import random
        
        current_price = 75000  # 임시 현재가
        
        # 랜덤한 신호 생성 (실제로는 기술적 분석, 기본적 분석 등 적용)
        signal_types = ["BUY", "SELL", "HOLD"]
        signal_type = random.choice(signal_types)
        
        confidence = random.randint(60, 95)  # 신뢰도 60-95%
        
        # 신호에 따른 목표가와 손절가 설정
        if signal_type == "BUY":
            price_target = current_price * 1.1  # 10% 상승 목표
            stop_loss = current_price * 0.95   # 5% 손절
            reasoning = "기술적 지표 상승 신호, 거래량 증가, RSI 과매도 구간 탈출"
        elif signal_type == "SELL":
            price_target = current_price * 0.9  # 10% 하락 예상
            stop_loss = current_price * 1.05   # 5% 손절
            reasoning = "기술적 지표 하락 신호, 고점 저항선 접근, RSI 과매수 구간"
        else:  # HOLD
            price_target = None
            stop_loss = None
            reasoning = "횡보 구간, 추가 관찰 필요, 방향성 불분명"
        
        # 분석 요소들
        analysis_factors = []
        if signal_type == "BUY":
            analysis_factors = [
                {"factor": "이동평균선", "status": "상승", "weight": 0.25},
                {"factor": "RSI", "status": "적정", "weight": 0.20},
                {"factor": "거래량", "status": "증가", "weight": 0.20},
                {"factor": "MACD", "status": "골든크로스", "weight": 0.15},
                {"factor": "볼린저밴드", "status": "하단지지", "weight": 0.20}
            ]
        elif signal_type == "SELL":
            analysis_factors = [
                {"factor": "이동평균선", "status": "하락", "weight": 0.25},
                {"factor": "RSI", "status": "과매수", "weight": 0.20},
                {"factor": "거래량", "status": "감소", "weight": 0.20},
                {"factor": "MACD", "status": "데드크로스", "weight": 0.15},
                {"factor": "볼린저밴드", "status": "상단저항", "weight": 0.20}
            ]
        else:
            analysis_factors = [
                {"factor": "이동평균선", "status": "혼조", "weight": 0.25},
                {"factor": "RSI", "status": "중립", "weight": 0.20},
                {"factor": "거래량", "status": "보통", "weight": 0.20},
                {"factor": "MACD", "status": "중립", "weight": 0.15},
                {"factor": "볼린저밴드", "status": "중간", "weight": 0.20}
            ]
        
        signal = TradingSignalResponse(
            stock_id=stock_id,
            signal_type=signal_type,
            confidence=confidence,
            current_price=current_price,
            price_target=price_target,
            stop_loss=stop_loss,
            reasoning=reasoning,
            analysis_factors=analysis_factors,
            timeframe="1D",  # 일봉 기준
            generated_at=datetime.now()
        )
        return create_response(signal.model_dump(), message="매매 신호 조회 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"매매 신호 조회 실패: {str(e)}")


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
        # 포트폴리오 요약 정보 조회
        portfolio_summary = portfolio_service.portfolio_repo.get_portfolio_summary(current_user_id)
        portfolios = portfolio_service.portfolio_repo.get_by_user_id(current_user_id, only_active=True)
        
        total_value = float(portfolio_summary['total_current_value'])
        
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


@router.post("/backtest", response_model=BacktestResponse, summary="백테스팅 실행")
async def run_backtest(
    backtest_request: BacktestRequest,
    current_user_id: str = Depends(get_current_user)
):
    """
    거래 전략의 백테스팅을 실행합니다.
    - 전략 성과 분석
    - 거래 내역 시뮬레이션
    - 리스크 지표 계산
    """
    try:
        import random
        from datetime import timedelta
        
        # 백테스트 기간 계산
        start_date = datetime.strptime(backtest_request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(backtest_request.end_date, "%Y-%m-%d")
        days = (end_date - start_date).days
        
        # 초기 자본
        initial_capital = backtest_request.initial_capital
        current_capital = initial_capital
        
        # 백테스트 시뮬레이션 (간단한 랜덤 결과)
        trade_history = []
        daily_returns = []
        equity_curve = []
        
        # 일별 수익률 생성 (랜덤)
        for i in range(days):
            date = start_date + timedelta(days=i)
            daily_return = random.uniform(-0.05, 0.05)  # -5% ~ +5% 일일 수익률
            daily_returns.append({
                "date": date.strftime("%Y-%m-%d"),
                "return": daily_return
            })
            
            current_capital *= (1 + daily_return)
            equity_curve.append({
                "date": date.strftime("%Y-%m-%d"),
                "value": current_capital
            })
        
        # 거래 내역 생성 (랜덤)
        num_trades = random.randint(20, 50)
        win_trades = 0
        
        for i in range(num_trades):
            trade_date = start_date + timedelta(days=random.randint(0, days-1))
            trade_type = random.choice(["BUY", "SELL"])
            profit_loss = random.uniform(-5000, 8000)  # -5000 ~ +8000 손익
            
            if profit_loss > 0:
                win_trades += 1
            
            trade_history.append({
                "date": trade_date.strftime("%Y-%m-%d"),
                "type": trade_type,
                "symbol": random.choice(["005930", "000660", "035420", "051910"]),
                "quantity": random.randint(10, 100),
                "price": random.randint(50000, 150000),
                "profit_loss": profit_loss
            })
        
        # 성과 지표 계산
        final_capital = current_capital
        total_return = (final_capital - initial_capital) / initial_capital
        annualized_return = (pow(final_capital / initial_capital, 365 / days) - 1) if days > 0 else 0
        
        # 최대 낙폭 계산 (간단 버전)
        peak = initial_capital
        max_drawdown = 0
        for point in equity_curve:
            value = point["value"]
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 샤프 비율 (간단 계산)
        if daily_returns:
            avg_return = sum(r["return"] for r in daily_returns) / len(daily_returns)
            return_std = (sum((r["return"] - avg_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe_ratio = (avg_return * 252) / (return_std * (252 ** 0.5)) if return_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        win_rate = (win_trades / num_trades * 100) if num_trades > 0 else 0
        
        backtest_result = BacktestResponse(
            strategy_name=backtest_request.strategy_name,
            period=f"{backtest_request.start_date} ~ {backtest_request.end_date}",
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return * 100,  # 퍼센트로 변환
            annualized_return=annualized_return * 100,
            max_drawdown=max_drawdown * 100,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            total_trades=num_trades,
            daily_returns=daily_returns,
            trade_history=trade_history,
            equity_curve=equity_curve,
            volatility=return_std * (252 ** 0.5) * 100 if 'return_std' in locals() else 15.0,
            profit_factor=1.5,  # 임시 값
            avg_win=sum(t["profit_loss"] for t in trade_history if t["profit_loss"] > 0) / win_trades if win_trades > 0 else 0,
            avg_loss=sum(t["profit_loss"] for t in trade_history if t["profit_loss"] < 0) / (num_trades - win_trades) if (num_trades - win_trades) > 0 else 0
        )
        return create_response(backtest_result.model_dump(), message="백테스팅 실행 성공")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"백테스팅 실행 실패: {str(e)}")


@router.get("/export/transactions", summary="거래 내역 내보내기")
async def export_transactions(
    format: str = Query("csv", description="내보내기 형식 (csv/excel)"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """거래 내역을 파일로 내보냅니다."""
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
        
        # 거래 내역 조회 (페이징 없이 전체)
        all_transactions = transaction_service.transaction_repo.get_by_user_id(
            user_id=current_user_id,
            offset=0,
            limit=10000,  # 충분히 큰 수
            start_date=parsed_start_date,
            end_date=parsed_end_date
        )
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transactions_{current_user_id}_{timestamp}.{format}"
        
        # 실제로는 파일을 생성하고 저장소에 업로드해야 함
        # 여기서는 임시로 URL만 반환
        download_url = f"/downloads/{filename}"
        
        # CSV/Excel 형식별 처리 (실제 구현에서는 pandas 등 사용)
        if format.lower() == "csv":
            # CSV 형식으로 변환
            csv_data = []
            headers = ["거래일시", "거래유형", "종목코드", "종목명", "수량", "가격", "거래금액", "수수료", "세금", "순거래금액"]
            csv_data.append(headers)
            
            for transaction in all_transactions:
                row = [
                    transaction.transaction_date.strftime("%Y-%m-%d %H:%M:%S"),
                    transaction.transaction_type.value,
                    transaction.stock_id or "",
                    f"주식 {transaction.stock_id}" if transaction.stock_id else "",
                    str(transaction.quantity) if transaction.quantity else "",
                    str(transaction.price) if transaction.price else "",
                    str(transaction.amount),
                    str(transaction.commission),
                    str(transaction.tax),
                    str(transaction.net_amount)
                ]
                csv_data.append(row)
            
            export_info = {
                "format": "CSV",
                "total_records": len(all_transactions),
                "columns": len(headers),
                "file_size_estimate": f"{len(all_transactions) * 100}B"  # 대략적인 크기
            }
        
        elif format.lower() == "excel":
            # Excel 형식으로 변환
            export_info = {
                "format": "Excel",
                "total_records": len(all_transactions),
                "sheets": ["거래내역", "요약"],
                "file_size_estimate": f"{len(all_transactions) * 150}B"  # 대략적인 크기
            }
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'csv' or 'excel'")
        
        return create_response(
            data={
                "download_url": download_url,
                "filename": filename,
                "export_info": export_info,
                "total_transactions": len(all_transactions),
                "generated_at": datetime.now().isoformat()
            },
            message=f"거래 내역 {format.upper()} 내보내기가 완료되었습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"거래 내역 내보내기 실패: {str(e)}")


@router.get("/reports/tax", summary="세금 신고용 자료")
async def get_tax_report(
    year: int = Query(..., description="신고 연도"),
    current_user_id: str = Depends(get_current_user),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """세금 신고용 거래 내역을 조회합니다."""
    try:
        # 해당 연도 거래 내역 조회
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        from app.db.models.transaction import TransactionType
        
        # 매도 거래만 조회 (세금 대상)
        sell_transactions = transaction_service.transaction_repo.get_by_user_id(
            user_id=current_user_id,
            offset=0,
            limit=10000,
            transaction_type=TransactionType.SELL,
            start_date=start_date,
            end_date=end_date
        )
        
        # 세금 신고용 데이터 계산
        tax_transactions = []
        total_profit_loss = 0
        total_tax_paid = 0
        
        for transaction in sell_transactions:
            # 각 매도 거래에 대한 손익 계산 (임시 계산)
            # 실제로는 FIFO, LIFO 등의 방식으로 매수가와 매도가를 매칭해야 함
            
            sell_amount = float(transaction.amount)
            # 간단한 손익 계산 (실제로는 더 복잡)
            estimated_buy_amount = sell_amount * 0.9  # 임시로 90% 가정
            profit_loss = sell_amount - estimated_buy_amount - float(transaction.commission) - float(transaction.tax)
            
            total_profit_loss += profit_loss
            total_tax_paid += float(transaction.tax)
            
            tax_transactions.append({
                "transaction_id": transaction.id,
                "transaction_date": transaction.transaction_date.strftime("%Y-%m-%d"),
                "stock_id": transaction.stock_id,
                "stock_name": f"주식 {transaction.stock_id}",
                "quantity": transaction.quantity,
                "sell_price": float(transaction.price),
                "sell_amount": sell_amount,
                "estimated_buy_amount": estimated_buy_amount,
                "profit_loss": profit_loss,
                "commission": float(transaction.commission),
                "tax_paid": float(transaction.tax),
                "net_profit_loss": profit_loss - float(transaction.tax)
            })
        
        # 세금 계산 (간단한 버전)
        # 실제로는 다양한 세금 규정을 적용해야 함
        taxable_income = max(0, total_profit_loss)  # 손실은 세금 대상 아님
        
        # 주식 양도소득세 (간단 계산)
        if taxable_income > 2500000:  # 250만원 기준공제
            tax_rate = 0.22  # 22% (지방세 포함)
            calculated_tax = (taxable_income - 2500000) * tax_rate
        else:
            calculated_tax = 0
        
        # 월별 거래 요약
        monthly_summary = transaction_service.transaction_repo.get_monthly_summary(current_user_id, year)
        
        # 종목별 손익 요약
        stock_summary = {}
        for transaction in sell_transactions:
            stock_id = transaction.stock_id
            if stock_id not in stock_summary:
                stock_summary[stock_id] = {
                    "stock_id": stock_id,
                    "stock_name": f"주식 {stock_id}",
                    "total_sell_amount": 0,
                    "total_quantity": 0,
                    "transaction_count": 0
                }
            
            stock_summary[stock_id]["total_sell_amount"] += float(transaction.amount)
            stock_summary[stock_id]["total_quantity"] += transaction.quantity
            stock_summary[stock_id]["transaction_count"] += 1
        
        tax_report = {
            "year": year,
            "reporting_period": f"{year}-01-01 ~ {year}-12-31",
            "summary": {
                "total_profit_loss": total_profit_loss,
                "taxable_income": taxable_income,
                "basic_deduction": 2500000,  # 기본공제
                "calculated_tax": calculated_tax,
                "tax_already_paid": total_tax_paid,
                "additional_tax_due": max(0, calculated_tax - total_tax_paid),
                "refund_amount": max(0, total_tax_paid - calculated_tax)
            },
            "transaction_summary": {
                "total_sell_transactions": len(sell_transactions),
                "total_sell_amount": sum(float(t.amount) for t in sell_transactions),
                "total_commission": sum(float(t.commission) for t in sell_transactions),
                "total_tax_paid": total_tax_paid
            },
            "monthly_summary": monthly_summary,
            "stock_summary": list(stock_summary.values()),
            "transactions": tax_transactions,
            "tax_calculation_method": "추정 계산 (실제 세무 신고시 정확한 계산 필요)",
            "generated_at": datetime.now().isoformat(),
            "disclaimer": "본 자료는 참고용이며, 실제 세무 신고시에는 세무사와 상담하시기 바랍니다."
        }
        
        return create_response(
            data=tax_report,
            message=f"{year}년 세금 신고용 자료가 생성되었습니다."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세금 신고 자료 생성 실패: {str(e)}")