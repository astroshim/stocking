from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date

from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.transaction_repository import TransactionRepository
from app.db.models.portfolio import Portfolio
from app.utils.simple_paging import SimplePage
from app.utils.data_converters import DataConverters


class PortfolioService:
    """포트폴리오 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.transaction_repo = TransactionRepository(db)
        # watchlist 관련 로직은 WatchListService로 이동

    def get_user_portfolio(
        self, 
        user_id: str,
        page: int = 1,
        size: int = 20,
        only_active: bool = True,
        include_orders: bool = False
    ) -> SimplePage:
        """사용자 포트폴리오 조회"""
        portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active, include_orders)
        
        # 페이징 처리
        offset = (page - 1) * size
        total_items = len(portfolios)
        paged_portfolios = portfolios[offset:offset + size]
        
        # 포트폴리오 데이터 변환
        portfolio_data = []
        for portfolio in paged_portfolios:
            item = DataConverters.convert_portfolio_to_dict(portfolio, include_orders)
            # 실현 손익률(%) = 누적 실현손익(KRW) / 누적 실현원가(KRW) * 100
            try:
                krw_realized = getattr(portfolio, 'krw_realized_profit_loss', None)
                if krw_realized is not None:
                    realized_cost = self.transaction_repo.get_realized_cost_krw_by_stock(portfolio.user_id, portfolio.product_code)
                    if realized_cost and realized_cost > 0:
                        item['realized_profit_loss_rate'] = float((Decimal(str(krw_realized)) / realized_cost) * Decimal('100'))
                    else:
                        item['realized_profit_loss_rate'] = None
                else:
                    item['realized_profit_loss_rate'] = None
            except Exception:
                item['realized_profit_loss_rate'] = None
            portfolio_data.append(item)
        
        return SimplePage(
            items=portfolio_data,
            page=page,
            per_page=size,
            has_next=offset + size < total_items
        )

    def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """포트폴리오 요약 정보 조회"""
        return self.portfolio_repo.get_portfolio_summary(user_id)

    def get_portfolio_analysis(self, user_id: str) -> Dict[str, Any]:
        """포트폴리오 분석 정보 조회"""
        sector_allocation = self.portfolio_repo.get_sector_allocation(user_id)
        top_holdings = self.portfolio_repo.get_top_holdings(user_id)
        
        # 성과 지표 계산
        summary = self.portfolio_repo.get_portfolio_summary(user_id)
        performance_metrics = {
            'total_return': float(summary['total_profit_loss']),
            'total_return_rate': float(summary['total_profit_loss_rate']),
            'total_invested': float(summary['total_invested_amount']),
            'current_value': float(summary['total_current_value'])
        }
        
        # 리스크 지표 (간단한 계산)
        risk_metrics = {
            'diversification_score': len(sector_allocation),  # 섹터 다양성
            'concentration_risk': (
                max([holding['current_value'] for holding in top_holdings], default=0) / 
                summary['total_current_value'] * 100
                if summary['total_current_value'] > 0 else 0
            )
        }
        
        return {
            'sector_allocation': sector_allocation,
            'top_holdings': top_holdings,
            'performance_metrics': performance_metrics,
            'risk_metrics': risk_metrics
        }

    def get_portfolio_by_stock(self, user_id: str, product_code: str) -> Optional[Dict[str, Any]]:
        """특정 종목 포트폴리오 조회 (product_code 기반)"""
        portfolio = self.portfolio_repo.get_by_user_and_stock(user_id, product_code)
        
        if not portfolio:
            return None
        
        item = DataConverters.convert_portfolio_to_dict(portfolio, include_orders=False)
        try:
            krw_realized = getattr(portfolio, 'krw_realized_profit_loss', None)
            if krw_realized is not None:
                realized_cost = self.transaction_repo.get_realized_cost_krw_by_stock(portfolio.user_id, product_code)
                if realized_cost and realized_cost > 0:
                    item['realized_profit_loss_rate'] = float((Decimal(str(krw_realized)) / realized_cost) * Decimal('100'))
                else:
                    item['realized_profit_loss_rate'] = None
            else:
                item['realized_profit_loss_rate'] = None
        except Exception:
            item['realized_profit_loss_rate'] = None
        return item
