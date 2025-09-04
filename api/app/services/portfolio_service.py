from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date

from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.watchlist_repository import WatchListRepository
from app.db.models.portfolio import Portfolio
from app.db.models.watchlist import WatchList, WatchlistDirectory
from app.utils.simple_paging import SimplePage
from app.utils.data_converters import DataConverters


class PortfolioService:
    """포트폴리오 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.watchlist_repo = WatchListRepository(db)

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
        portfolio_data = [
            DataConverters.convert_portfolio_to_dict(portfolio)
            for portfolio in paged_portfolios
        ]
        
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
        
        return DataConverters.convert_portfolio_to_dict(portfolio)



    def add_to_watchlist(
        self,
        user_id: str,
        product_code: str,
        directory_id: Optional[str] = None,
        category: str = "기본",
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """관심 종목 추가"""
        try:
            # 디렉토리가 지정되지 않은 경우 기본 디렉토리 사용
            if not directory_id:
                default_directory = self.watchlist_repo.ensure_default_directory(user_id)
                directory_id = default_directory.id
            
            watchlist = self.watchlist_repo.create_watchlist(
                user_id=user_id,
                product_code=product_code,
                directory_id=directory_id,
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
        # Repository에서 페이징 처리된 결과를 가져옴
        page_result = self.watchlist_repo.get_by_user_id(
            user_id=user_id,
            category=category,
            page=page,
            per_page=size
        )
        
        # 관심 종목 데이터 변환
        watchlist_data = [
            DataConverters.convert_watchlist_to_dict(
                watchlist, 
                include_product_details=True,
                current_price=None  # TODO: 외부 API에서 현재가 조회
            )
            for watchlist in page_result.items
        ]
        
        return SimplePage(
            items=watchlist_data,
            page=page_result.page,
            per_page=page_result.per_page,
            has_next=page_result.has_next
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

    # ========== 관심종목 디렉토리 관련 메서드 ==========

    def create_watchlist_directory(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
        """관심종목 디렉토리 생성"""
        try:
            directory = self.watchlist_repo.create_directory(
                user_id=user_id,
                name=name,
                description=description,
                color=color
            )
            self.db.commit()
            return directory
        except Exception as e:
            self.db.rollback()
            raise e

    def get_watchlist_directories(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20
    ) -> SimplePage:
        """사용자의 관심종목 디렉토리 목록 조회"""
        # 기본 디렉토리 자동 생성 (기존 사용자 대응)
        try:
            self.watchlist_repo.ensure_default_directory(user_id)
            self.db.commit()
        except Exception as e:
            print(f"⚠️ 기본 디렉토리 생성 실패: {e}")
            self.db.rollback()
        
        # Repository에서 페이징 처리된 결과를 가져옴
        page_result = self.watchlist_repo.get_directories_with_stats(user_id, page=page, per_page=size)
        
        # 응답 데이터 변환
        directory_data = [
            DataConverters.convert_directory_to_dict(
                item['directory'],
                include_stats=True,
                watchlist_count=item['watchlist_count']
            )
            for item in page_result.items
        ]
        
        return SimplePage(
            items=directory_data,
            page=page_result.page,
            per_page=page_result.per_page,
            has_next=page_result.has_next
        )

    def get_watchlist_directory(self, user_id: str, directory_id: str) -> Optional[Dict[str, Any]]:
        """관심종목 디렉토리 상세 조회 (디렉토리 내 관심종목 포함)"""
        result = self.watchlist_repo.get_directory_with_watchlists(directory_id, user_id)
        if not result:
            return None
        
        directory = result['directory']
        watchlists = result['watch_lists']
        
        # 관심종목 데이터 변환
        watchlist_data = [
            DataConverters.convert_watchlist_to_dict(
                watchlist, 
                include_product_details=True,
                current_price=None  # TODO: 외부 API에서 현재가 조회
            )
            for watchlist in watchlists
        ]
        
        directory_dict = DataConverters.convert_directory_to_dict(directory)
        directory_dict['watch_lists'] = watchlist_data
        return directory_dict

    def update_watchlist_directory(
        self,
        user_id: str,
        directory_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
        """관심종목 디렉토리 수정"""
        directory = self.watchlist_repo.get_directory_by_id_and_user(directory_id, user_id)
        if not directory:
            raise ValueError("디렉토리를 찾을 수 없습니다")
        
        try:
            updated_directory = self.watchlist_repo.update_directory(
                directory=directory,
                name=name,
                description=description,
                color=color
            )
            self.db.commit()
            return updated_directory
        except Exception as e:
            self.db.rollback()
            raise e

    def delete_watchlist_directory(self, user_id: str, directory_id: str):
        """관심종목 디렉토리 삭제"""
        # 기본 디렉토리는 삭제할 수 없음
        default_directory_id = f"{user_id}-base"
        if directory_id == default_directory_id:
            raise ValueError("기본 디렉토리는 삭제할 수 없습니다")
        
        directory = self.watchlist_repo.get_directory_by_id_and_user(directory_id, user_id)
        if not directory:
            raise ValueError("디렉토리를 찾을 수 없습니다")
        
        try:
            self.watchlist_repo.delete_directory(directory)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def get_default_directory(self, user_id: str) -> Dict[str, Any]:
        """사용자의 기본 디렉토리 조회"""
        # 기본 디렉토리 자동 생성
        default_directory = self.watchlist_repo.ensure_default_directory(user_id)
        
        return DataConverters.convert_directory_to_dict(default_directory)