from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.repositories.watchlist_repository import WatchListRepository
from app.db.models.watchlist import WatchList, WatchlistDirectory
from app.utils.simple_paging import SimplePage
from app.utils.data_converters import DataConverters
from app.services.toss_proxy_service import TossProxyService
from app.exceptions.custom_exceptions import ValidationError


class WatchListService:
    """관심종목(WatchList) 및 디렉토리 서비스"""

    def __init__(self, db: Session, toss_proxy_service: TossProxyService | None = None):
        self.db = db
        self.watchlist_repo = WatchListRepository(db)
        self.toss_proxy_service = toss_proxy_service or TossProxyService()

    # ========== 관심종목 CRUD ==========
    def add_to_watchlist(
        self,
        user_id: str,
        product_code: str,
        directory_id: Optional[str] = None,
        category: str = "기본",
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        try:
            # product_code 유효성 검사: 'US' 또는 'A'로 시작
            if not (product_code.startswith('US') or product_code.startswith('A')):
                raise ValidationError("product_code는 'US' 또는 'A'로 시작해야 합니다")

            # 디렉토리가 지정되지 않은 경우 기본 디렉토리 사용
            if not directory_id:
                default_directory = self.watchlist_repo.ensure_default_directory(user_id)
                directory_id = default_directory.id

            # Toss 오버뷰로 product_name, market 조회
            product_name = product_code
            market = 'UNKNOWN'
            try:
                overview_raw = self.toss_proxy_service.get_stock_overview(product_code)
                ov = overview_raw.get('result') if isinstance(overview_raw, dict) else None
                company = (ov or {}).get('company', {}) if isinstance(ov, dict) else {}
                market_info = (ov or {}).get('market', {}) if isinstance(ov, dict) else {}
                product_name = company.get('fullName') or company.get('name') or product_code
                market = market_info.get('displayName') or market_info.get('code') or 'UNKNOWN'
            except Exception:
                pass

            watchlist = self.watchlist_repo.create_watchlist(
                user_id=user_id,
                product_code=product_code,
                directory_id=directory_id,
                category=category,
                memo=memo,
                target_price=target_price,
                product_name=product_name,
                market=market
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
        # Repository에서 페이징 처리된 결과를 가져옴
        page_result = self.watchlist_repo.get_by_user_id(
            user_id=user_id,
            category=category,
            page=page,
            per_page=size
        )

        # 관심 종목 데이터 변환 + 주가 상세 포함
        watchlist_data = []
        for watchlist in page_result.items:
            item = DataConverters.convert_watchlist_to_dict(
                watchlist,
                include_product_details=True,
                current_price=None
            )
            try:
                price_raw = self.toss_proxy_service.get_stock_price_details(watchlist.product_code)
                # 그대로 응답에 포함 (스키마에서 검증)
                item['stock_price_details'] = price_raw
            except Exception:
                item['stock_price_details'] = None
            watchlist_data.append(item)

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
        return self.watchlist_repo.get_categories_with_count(user_id)

    # ========== 디렉토리 ==========
    def create_watchlist_directory(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
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

    def get_watchlist_directories(self, user_id: str, page: int = 1, size: int = 20) -> SimplePage:
        try:
            self.watchlist_repo.ensure_default_directory(user_id)
            self.db.commit()
        except Exception as e:
            print(f"⚠️ 기본 디렉토리 생성 실패: {e}")
            self.db.rollback()

        page_result = self.watchlist_repo.get_directories_with_stats(user_id, page=page, per_page=size)

        directory_data = [
            DataConverters.convert_directory_to_dict(
                item['directory'], include_stats=True, watchlist_count=item['watchlist_count']
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
        result = self.watchlist_repo.get_directory_with_watchlists(directory_id, user_id)
        if not result:
            return None

        directory = result['directory']
        watchlists = result['watch_lists']
        watchlist_data = []
        for watchlist in watchlists:
            item = DataConverters.convert_watchlist_to_dict(
                watchlist, include_product_details=True, current_price=None
            )
            try:
                price_raw = self.toss_proxy_service.get_stock_price_details(watchlist.product_code)
                item['stock_price_details'] = price_raw
            except Exception:
                item['stock_price_details'] = None
            watchlist_data.append(item)

        directory_dict = DataConverters.convert_directory_to_dict(directory)
        directory_dict['watch_lists'] = watchlist_data
        return directory_dict

    def get_default_directory(self, user_id: str) -> Dict[str, Any]:
        default_directory = self.watchlist_repo.ensure_default_directory(user_id)
        return DataConverters.convert_directory_to_dict(default_directory)

    def update_watchlist_directory(
        self,
        user_id: str,
        directory_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
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
        # 기본 디렉토리는 삭제 불가
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


