from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func

from app.db.repositories.base_repository import BaseRepository
from app.db.models.transaction import WatchList
from app.db.models.stock import Stock, StockPrice


class WatchListRepository(BaseRepository):
    """관심 종목 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_user_id(
        self, 
        user_id: str, 
        category: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> List[WatchList]:
        """사용자의 관심 종목 목록 조회"""
        query = self.session.query(WatchList).filter(WatchList.user_id == user_id)
        
        if category:
            query = query.filter(WatchList.category == category)
        
        return query.options(
            joinedload(WatchList.stock).joinedload(Stock.current_price)
        ).order_by(
            WatchList.display_order.asc(),
            WatchList.created_at.desc()
        ).offset(offset).limit(limit).all()

    def get_by_user_and_stock(self, user_id: str, stock_id: str) -> Optional[WatchList]:
        """사용자의 특정 종목 관심 목록 조회"""
        return self.session.query(WatchList).filter(
            and_(
                WatchList.user_id == user_id,
                WatchList.stock_id == stock_id
            )
        ).first()

    def get_by_id_and_user(self, watchlist_id: str, user_id: str) -> Optional[WatchList]:
        """ID와 사용자로 관심 종목 조회"""
        return self.session.query(WatchList).filter(
            and_(
                WatchList.id == watchlist_id,
                WatchList.user_id == user_id
            )
        ).options(
            joinedload(WatchList.stock).joinedload(Stock.current_price)
        ).first()

    def create_watchlist(
        self,
        user_id: str,
        stock_id: str,
        category: str = "기본",
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """새 관심 종목 추가"""
        # 기존에 같은 종목이 있는지 확인
        existing = self.get_by_user_and_stock(user_id, stock_id)
        if existing:
            raise ValueError("이미 관심 종목에 추가된 주식입니다")
        
        # 다음 표시 순서 계산
        max_order = self.session.query(
            func.max(WatchList.display_order)
        ).filter(
            and_(
                WatchList.user_id == user_id,
                WatchList.category == category
            )
        ).scalar() or 0
        
        watchlist = WatchList(
            user_id=user_id,
            stock_id=stock_id,
            category=category,
            memo=memo,
            target_price=target_price,
            display_order=max_order + 1
        )
        
        self.session.add(watchlist)
        self.session.flush()
        return watchlist

    def update_watchlist(
        self,
        watchlist: WatchList,
        category: Optional[str] = None,
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """관심 종목 정보 수정"""
        if category is not None:
            watchlist.category = category
        if memo is not None:
            watchlist.memo = memo
        if target_price is not None:
            watchlist.target_price = target_price
        
        return watchlist

    def delete_watchlist(self, watchlist: WatchList):
        """관심 종목 삭제"""
        # 삭제된 항목보다 높은 순서의 항목들을 한 칸씩 앞으로 이동
        self.session.query(WatchList).filter(
            and_(
                WatchList.user_id == watchlist.user_id,
                WatchList.category == watchlist.category,
                WatchList.display_order > watchlist.display_order
            )
        ).update({
            WatchList.display_order: WatchList.display_order - 1
        })
        
        self.session.delete(watchlist)

    def reorder_watchlist(
        self,
        watchlist: WatchList,
        new_order: int
    ) -> WatchList:
        """관심 종목 순서 변경"""
        old_order = watchlist.display_order
        
        if old_order == new_order:
            return watchlist
        
        # 같은 카테고리 내에서 순서 조정
        if old_order < new_order:
            # 아래로 이동: 중간 항목들을 위로 이동
            self.session.query(WatchList).filter(
                and_(
                    WatchList.user_id == watchlist.user_id,
                    WatchList.category == watchlist.category,
                    WatchList.display_order > old_order,
                    WatchList.display_order <= new_order
                )
            ).update({
                WatchList.display_order: WatchList.display_order - 1
            })
        else:
            # 위로 이동: 중간 항목들을 아래로 이동
            self.session.query(WatchList).filter(
                and_(
                    WatchList.user_id == watchlist.user_id,
                    WatchList.category == watchlist.category,
                    WatchList.display_order >= new_order,
                    WatchList.display_order < old_order
                )
            ).update({
                WatchList.display_order: WatchList.display_order + 1
            })
        
        watchlist.display_order = new_order
        return watchlist

    def get_categories_with_count(self, user_id: str) -> List[Dict]:
        """사용자의 관심 종목 카테고리별 개수 조회"""
        result = self.session.query(
            WatchList.category,
            func.count(WatchList.id).label('count')
        ).filter(
            WatchList.user_id == user_id
        ).group_by(
            WatchList.category
        ).all()
        
        categories = []
        for category, count in result:
            categories.append({
                'name': category,
                'count': count
            })
        
        # 기본 카테고리들이 없으면 추가 (개수 0으로)
        existing_categories = {cat['name'] for cat in categories}
        default_categories = ["기본", "관심주", "배당주", "성장주"]
        
        for default_cat in default_categories:
            if default_cat not in existing_categories:
                categories.append({
                    'name': default_cat,
                    'count': 0
                })
        
        return categories

    def count_by_user_id(self, user_id: str, category: Optional[str] = None) -> int:
        """사용자의 관심 종목 개수 조회"""
        query = self.session.query(WatchList).filter(WatchList.user_id == user_id)
        
        if category:
            query = query.filter(WatchList.category == category)
        
        return query.count()

    def check_target_price_alerts(self, user_id: str) -> List[WatchList]:
        """목표가 알림 대상 조회"""
        return self.session.query(WatchList).join(
            Stock
        ).join(
            StockPrice
        ).filter(
            and_(
                WatchList.user_id == user_id,
                WatchList.target_price.isnot(None),
                WatchList.target_price <= StockPrice.current_price
            )
        ).options(
            joinedload(WatchList.stock).joinedload(Stock.current_price)
        ).all()
