from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date

from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.watchlist_repository import WatchListRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.models.portfolio import Portfolio, VirtualBalanceHistory
from app.db.models.transaction import WatchList
from app.utils.simple_paging import SimplePage


class PortfolioService:
    """포트폴리오 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.watchlist_repo = WatchListRepository(db)
        self.virtual_balance_repo = VirtualBalanceRepository(db)

    def get_user_portfolio(
        self, 
        user_id: str,
        page: int = 1,
        size: int = 20,
        only_active: bool = True
    ) -> SimplePage:
        """사용자 포트폴리오 조회"""
        portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active)
        
        # 페이징 처리
        offset = (page - 1) * size
        total_items = len(portfolios)
        paged_portfolios = portfolios[offset:offset + size]
        
        # 포트폴리오 데이터 변환
        portfolio_data = []
        for portfolio in paged_portfolios:
            current_price = (
                portfolio.stock.current_price.current_price 
                if portfolio.stock.current_price 
                else Decimal('0')
            )
            
            current_value = portfolio.current_quantity * current_price
            invested_amount = portfolio.current_quantity * portfolio.average_price
            profit_loss = current_value - invested_amount
            profit_loss_rate = (
                (profit_loss / invested_amount * 100) 
                if invested_amount > 0 else Decimal('0')
            )
            
            portfolio_data.append({
                'id': portfolio.id,
                'stock_id': portfolio.stock_id,
                'stock_code': portfolio.stock.code,
                'stock_name': portfolio.stock.name,
                'market': portfolio.stock.market,
                'sector': portfolio.stock.sector,
                'current_quantity': portfolio.current_quantity,
                'average_price': float(portfolio.average_price),
                'current_price': float(current_price),
                'current_value': float(current_value),
                'invested_amount': float(invested_amount),
                'profit_loss': float(profit_loss),
                'profit_loss_rate': float(profit_loss_rate),
                'updated_at': portfolio.updated_at.isoformat()
            })
        
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

    def get_portfolio_by_stock(self, user_id: str, stock_id: str) -> Optional[Dict[str, Any]]:
        """특정 종목 포트폴리오 조회"""
        portfolio = self.portfolio_repo.get_by_user_and_stock(user_id, stock_id)
        
        if not portfolio:
            return None
        
        current_price = (
            portfolio.stock.current_price.current_price 
            if portfolio.stock.current_price 
            else Decimal('0')
        )
        
        current_value = portfolio.current_quantity * current_price
        invested_amount = portfolio.current_quantity * portfolio.average_price
        profit_loss = current_value - invested_amount
        profit_loss_rate = (
            (profit_loss / invested_amount * 100) 
            if invested_amount > 0 else Decimal('0')
        )
        
        return {
            'id': portfolio.id,
            'stock': {
                'id': portfolio.stock.id,
                'code': portfolio.stock.code,
                'name': portfolio.stock.name,
                'market': portfolio.stock.market,
                'sector': portfolio.stock.sector,
                'industry': portfolio.stock.industry,
                'current_price': float(current_price),
                'price_change': 0,  # TODO: 전일대비 변동률 계산
                'price_change_rate': 0
            },
            'current_quantity': portfolio.current_quantity,
            'total_quantity': portfolio.total_quantity,
            'average_price': float(portfolio.average_price),
            'total_invested_amount': float(portfolio.total_invested_amount),
            'current_value': float(current_value),
            'profit_loss': float(profit_loss),
            'profit_loss_rate': float(profit_loss_rate),
            'realized_profit_loss': float(portfolio.realized_profit_loss),
            'created_at': portfolio.created_at.isoformat(),
            'updated_at': portfolio.updated_at.isoformat()
        }

    def get_balance_history(
        self,
        user_id: str,
        page: int = 1,
        size: int = 50,
        change_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """잔고 변동 이력 조회"""
        # VirtualBalanceHistory 모델에서 조회
        # TODO: 실제 구현 시 날짜 필터링 및 타입 필터링 추가
        
        # 임시로 빈 리스트 반환
        return []

    def add_to_watchlist(
        self,
        user_id: str,
        stock_id: str,
        category: str = "기본",
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """관심 종목 추가"""
        try:
            watchlist = self.watchlist_repo.create_watchlist(
                user_id=user_id,
                stock_id=stock_id,
                category=category,
                memo=memo,
                target_price=target_price
            )
            self.db.commit()
            return watchlist
        except Exception as e:
            self.db.rollback()
            raise e

    def get_watchlist(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        category: Optional[str] = None
    ) -> SimplePage:
        """관심 종목 목록 조회"""
        offset = (page - 1) * size
        watchlists = self.watchlist_repo.get_by_user_id(
            user_id=user_id,
            category=category,
            offset=offset,
            limit=size
        )
        
        total_count = self.watchlist_repo.count_by_user_id(user_id, category)
        
        # 관심 종목 데이터 변환
        watchlist_data = []
        for watchlist in watchlists:
            current_price = (
                watchlist.stock.current_price.current_price 
                if watchlist.stock.current_price 
                else Decimal('0')
            )
            
            # 목표가 대비 변동률 계산
            target_achievement = None
            if watchlist.target_price and watchlist.target_price > 0:
                target_achievement = float(
                    (current_price - Decimal(str(watchlist.target_price))) / 
                    Decimal(str(watchlist.target_price)) * 100
                )
            
            watchlist_data.append({
                'id': watchlist.id,
                'stock': {
                    'id': watchlist.stock.id,
                    'code': watchlist.stock.code,
                    'name': watchlist.stock.name,
                    'market': watchlist.stock.market,
                    'sector': watchlist.stock.sector,
                    'current_price': float(current_price),
                    'price_change': 0,  # TODO: 전일대비 변동률 계산
                    'price_change_rate': 0
                },
                'category': watchlist.category,
                'memo': watchlist.memo,
                'target_price': watchlist.target_price,
                'target_achievement': target_achievement,
                'display_order': watchlist.display_order,
                'created_at': watchlist.created_at.isoformat()
            })
        
        return SimplePage(
            items=watchlist_data,
            page=page,
            per_page=size,
            has_next=offset + size < total_count
        )

    def update_watchlist(
        self,
        user_id: str,
        watchlist_id: str,
        category: Optional[str] = None,
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """관심 종목 수정"""
        watchlist = self.watchlist_repo.get_by_id_and_user(watchlist_id, user_id)
        if not watchlist:
            raise ValueError("관심 종목을 찾을 수 없습니다")
        
        try:
            updated_watchlist = self.watchlist_repo.update_watchlist(
                watchlist=watchlist,
                category=category,
                memo=memo,
                target_price=target_price
            )
            self.db.commit()
            return updated_watchlist
        except Exception as e:
            self.db.rollback()
            raise e

    def remove_from_watchlist(self, user_id: str, watchlist_id: str):
        """관심 종목 삭제"""
        watchlist = self.watchlist_repo.get_by_id_and_user(watchlist_id, user_id)
        if not watchlist:
            raise ValueError("관심 종목을 찾을 수 없습니다")
        
        try:
            self.watchlist_repo.delete_watchlist(watchlist)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def reorder_watchlist(self, user_id: str, watchlist_id: str, new_order: int):
        """관심 종목 순서 변경"""
        watchlist = self.watchlist_repo.get_by_id_and_user(watchlist_id, user_id)
        if not watchlist:
            raise ValueError("관심 종목을 찾을 수 없습니다")
        
        try:
            self.watchlist_repo.reorder_watchlist(watchlist, new_order)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def get_watchlist_categories(self, user_id: str) -> List[Dict[str, Any]]:
        """관심 종목 카테고리 목록 조회"""
        return self.watchlist_repo.get_categories_with_count(user_id)