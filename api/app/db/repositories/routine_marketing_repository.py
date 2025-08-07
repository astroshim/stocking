from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.repositories.base_repository import BaseRepository
from app.db.models.routine_marketing import RoutineMarketing
from app.utils.simple_paging import paginate_without_count, SimplePage
from typing import Optional


class RoutineMarketingRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_id(self, id: str) -> Optional[RoutineMarketing]:
        """ID로 루틴 마케팅 정보 조회"""
        return self.session.query(RoutineMarketing).filter_by(id=id).first()

    def list_routine_marketing(self, page: int = 1, per_page: int = 10) -> SimplePage:
        """루틴 마케팅 리스트 조회 (페이징 처리)"""
        query = self.session.query(RoutineMarketing).order_by(desc(RoutineMarketing.created_at))
        return paginate_without_count(query, page, per_page)

    def delete_by_id(self, id: str) -> bool:
        """ID로 루틴 마케팅 정보 삭제"""
        routine_marketing = self.get_by_id(id)
        if routine_marketing:
            self.delete(routine_marketing)
            return True
        return False 