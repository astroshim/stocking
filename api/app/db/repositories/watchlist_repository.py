from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func

from app.db.repositories.base_repository import BaseRepository
from app.db.models.watchlist import WatchList, WatchlistDirectory
from app.db.models.stock import Stock, StockPrice
from app.utils.simple_paging import SimplePage, paginate_without_count


class WatchListRepository(BaseRepository):
    """관심 종목 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_user_id(
        self, 
        user_id: str, 
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> SimplePage:
        """사용자의 관심 종목 목록 조회 (페이징)"""
        query = self.session.query(WatchList).filter(WatchList.user_id == user_id)
        
        if category:
            query = query.filter(WatchList.category == category)
        
        query = query.options(
            joinedload(WatchList.stock).joinedload(Stock.current_price)
        ).order_by(
            WatchList.display_order.asc(),
            WatchList.created_at.desc()
        )
        
        return paginate_without_count(query, page=page, per_page=per_page)

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
        directory_id: Optional[str] = None,
        category: str = "기본",
        memo: Optional[str] = None,
        target_price: Optional[float] = None
    ) -> WatchList:
        """새 관심 종목 추가"""
        # 기존에 같은 종목이 있는지 확인
        existing = self.get_by_user_and_stock(user_id, stock_id)
        if existing:
            raise ValueError("이미 관심 종목에 추가된 주식입니다")
        
        # 디렉토리가 지정된 경우 존재하는지 확인
        if directory_id:
            directory = self.get_directory_by_id_and_user(directory_id, user_id)
            if not directory:
                raise ValueError("존재하지 않는 디렉토리입니다")
        
        # 다음 표시 순서 계산 (디렉토리별로 분리)
        filter_conditions = [WatchList.user_id == user_id]
        if directory_id:
            filter_conditions.append(WatchList.directory_id == directory_id)
        else:
            filter_conditions.append(WatchList.category == category)
        
        max_order = self.session.query(
            func.max(WatchList.display_order)
        ).filter(and_(*filter_conditions)).scalar() or 0
        
        watchlist = WatchList(
            user_id=user_id,
            stock_id=stock_id,
            directory_id=directory_id,
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
        
        # # 기본 카테고리들이 없으면 추가 (개수 0으로)
        # existing_categories = {cat['name'] for cat in categories}
        # default_categories = ["기본", "관심주", "배당주", "성장주"]
        
        # for default_cat in default_categories:
        #     if default_cat not in existing_categories:
        #         categories.append({
        #             'name': default_cat,
        #             'count': 0
        #         })
        
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

    # ========== 관심종목 디렉토리 관련 메서드 ==========
    
    def get_directories_by_user_id(
        self, 
        user_id: str,
        offset: int = 0,
        limit: int = 20
    ) -> List[WatchlistDirectory]:
        """사용자의 관심종목 디렉토리 목록 조회"""
        return self.session.query(WatchlistDirectory).filter(
            and_(
                WatchlistDirectory.user_id == user_id,
                WatchlistDirectory.is_active == True
            )
        ).order_by(
            WatchlistDirectory.display_order.asc(),
            WatchlistDirectory.created_at.desc()
        ).offset(offset).limit(limit).all()

    def get_directory_by_id_and_user(self, directory_id: str, user_id: str) -> Optional[WatchlistDirectory]:
        """ID와 사용자로 디렉토리 조회"""
        return self.session.query(WatchlistDirectory).filter(
            and_(
                WatchlistDirectory.id == directory_id,
                WatchlistDirectory.user_id == user_id,
                WatchlistDirectory.is_active == True
            )
        ).first()

    def get_directory_by_name_and_user(self, name: str, user_id: str) -> Optional[WatchlistDirectory]:
        """이름과 사용자로 디렉토리 조회"""
        return self.session.query(WatchlistDirectory).filter(
            and_(
                WatchlistDirectory.name == name,
                WatchlistDirectory.user_id == user_id,
                WatchlistDirectory.is_active == True
            )
        ).first()

    def create_directory(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
        """새 관심종목 디렉토리 생성"""
        # 같은 이름의 디렉토리가 이미 있는지 확인
        existing = self.get_directory_by_name_and_user(name, user_id)
        if existing:
            raise ValueError("이미 존재하는 디렉토리 이름입니다")
        
        # 다음 표시 순서 계산
        max_order = self.session.query(
            func.max(WatchlistDirectory.display_order)
        ).filter(WatchlistDirectory.user_id == user_id).scalar() or 0
        
        directory = WatchlistDirectory(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            display_order=max_order + 1
        )
        
        self.session.add(directory)
        self.session.flush()
        return directory

    def update_directory(
        self,
        directory: WatchlistDirectory,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
        """관심종목 디렉토리 정보 수정"""
        # 이름 변경 시 중복 확인
        if name and name != directory.name:
            existing = self.get_directory_by_name_and_user(name, directory.user_id)
            if existing:
                raise ValueError("이미 존재하는 디렉토리 이름입니다")
            directory.name = name
        
        if description is not None:
            directory.description = description
        if color is not None:
            directory.color = color
        
        return directory

    def delete_directory(self, directory: WatchlistDirectory):
        """관심종목 디렉토리 삭제"""
        # 디렉토리 내 관심종목들을 category 기반으로 변경
        self.session.query(WatchList).filter(
            WatchList.directory_id == directory.id
        ).update({
            WatchList.directory_id: None,
            WatchList.category: "기본"
        })
        
        # 삭제된 디렉토리보다 높은 순서의 디렉토리들을 한 칸씩 앞으로 이동
        self.session.query(WatchlistDirectory).filter(
            and_(
                WatchlistDirectory.user_id == directory.user_id,
                WatchlistDirectory.display_order > directory.display_order
            )
        ).update({
            WatchlistDirectory.display_order: WatchlistDirectory.display_order - 1
        })
        
        self.session.delete(directory)

    def get_directories_with_stats(self, user_id: str, page: int = 1, per_page: int = 20) -> SimplePage:
        """사용자의 디렉토리 목록과 관심종목 개수 조회 (페이징)"""
        # 디렉토리별 관심종목 개수를 함께 조회하는 쿼리
        query = self.session.query(
            WatchlistDirectory,
            func.count(WatchList.id).label('watchlist_count')
        ).outerjoin(
            WatchList, and_(
                WatchlistDirectory.id == WatchList.directory_id,
                WatchList.is_active == True
            )
        ).filter(
            and_(
                WatchlistDirectory.user_id == user_id,
                WatchlistDirectory.is_active == True
            )
        ).group_by(WatchlistDirectory.id).order_by(
            WatchlistDirectory.display_order.asc(),
            WatchlistDirectory.created_at.desc()
        )
        
        # paginate_without_count 사용하여 페이징 처리
        page_result = paginate_without_count(query, page=page, per_page=per_page)
        
        # 결과를 Dictionary 형태로 변환
        directories = []
        for directory, count in page_result.items:
            directories.append({
                'directory': directory,
                'watchlist_count': count
            })
        
        # 변환된 데이터로 새로운 SimplePage 반환
        return SimplePage(
            items=directories,
            page=page_result.page,
            per_page=page_result.per_page,
            has_next=page_result.has_next
        )

    def get_directory_with_watchlists(self, directory_id: str, user_id: str) -> Optional[Dict]:
        """디렉토리와 해당 디렉토리의 관심종목 목록 조회"""
        directory = self.get_directory_by_id_and_user(directory_id, user_id)
        if not directory:
            return None
        
        watchlists = self.session.query(WatchList).filter(
            and_(
                WatchList.directory_id == directory_id,
                WatchList.is_active == True
            )
        ).options(
            joinedload(WatchList.stock).joinedload(Stock.current_price)
        ).order_by(
            WatchList.display_order.asc(),
            WatchList.created_at.desc()
        ).all()
        
        return {
            'directory': directory,
            'watch_lists': watchlists
        }

    def count_directories_by_user_id(self, user_id: str) -> int:
        """사용자의 디렉토리 개수 조회"""
        return self.session.query(WatchlistDirectory).filter(
            and_(
                WatchlistDirectory.user_id == user_id,
                WatchlistDirectory.is_active == True
            )
        ).count()

    def ensure_default_directory(self, user_id: str) -> WatchlistDirectory:
        """사용자의 기본 디렉토리 존재 확인 및 생성"""
        # 예측 가능한 기본 디렉토리 ID 생성
        default_directory_id = f"{user_id}-base"
        
        # ID로 먼저 조회 시도
        default_directory = self.get_directory_by_id_and_user(default_directory_id, user_id)
        
        if not default_directory:
            # 이름으로도 확인 (마이그레이션 대응)
            default_directory = self.get_directory_by_name_and_user("기본", user_id)
        
        if not default_directory:
            # 기본 디렉토리가 없으면 생성 (사용자 정의 ID 사용)
            default_directory = self._create_directory_with_id(
                directory_id=default_directory_id,
                user_id=user_id,
                name="기본",
                description="기본 관심종목 디렉토리",
                color="#007bff"  # 파란색
            )
            print(f"✅ 사용자 {user_id}의 기본 디렉토리 자동 생성 완료 (ID: {default_directory_id})")
        
        return default_directory

    def _create_directory_with_id(
        self,
        directory_id: str,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> WatchlistDirectory:
        """지정된 ID로 관심종목 디렉토리 생성 (내부 메서드)"""
        # 같은 이름의 디렉토리가 이미 있는지 확인
        existing = self.get_directory_by_name_and_user(name, user_id)
        if existing:
            raise ValueError("이미 존재하는 디렉토리 이름입니다")
        
        # 다음 표시 순서 계산
        max_order = self.session.query(
            func.max(WatchlistDirectory.display_order)
        ).filter(WatchlistDirectory.user_id == user_id).scalar() or 0
        
        # 사용자 정의 ID로 디렉토리 생성
        directory = WatchlistDirectory(
            id=directory_id,  # 직접 ID 지정
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            display_order=max_order + 1
        )
        
        self.session.add(directory)
        self.session.flush()
        return directory

    def get_default_directory(self, user_id: str) -> Optional[WatchlistDirectory]:
        """사용자의 기본 디렉토리 조회 (예측 가능한 ID 사용)"""
        default_directory_id = f"{user_id}-base"
        return self.get_directory_by_id_and_user(default_directory_id, user_id)
