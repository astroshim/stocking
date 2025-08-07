from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.notice import Notice
from app.db.repositories.base_repository import BaseRepository
from app.utils.simple_paging import SimplePage, paginate_without_count


class NoticeRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_id(self, notice_id: str) -> Optional[Notice]:
        """ID로 공지사항 조회"""
        return self.session.get(Notice, notice_id)

    def get_by_id_and_user(self, user_id: str, notice_id: str) -> Optional[Notice]:
        """ID와 사용자 ID로 공지사항 조회"""
        return self.session.query(Notice).filter_by(id=notice_id, creator_id=user_id).first()

    def list_active_notices(self, page: int = 1, per_page: int = 10) -> SimplePage:
        """활성화된 공지사항 목록 조회"""
        query = self.session.query(Notice).filter_by(is_active=True).order_by(Notice.created_at.desc())
        return paginate_without_count(query, page=page, per_page=per_page)

    def list_notices(self, status: str = 'all', page: int = 1, per_page: int = 10) -> SimplePage:
        """모든 공지사항 목록 조회"""
        # 기본 쿼리 생성 (생성일 기준 내림차순)
        query = self.session.query(Notice).order_by(Notice.created_at.desc())

        # 상태에 따른 필터 적용
        status_filters = {
            'active': {'is_active': True},
            'inactive': {'is_active': False}
        }

        # status가 'all'이 아닐 경우 필터 적용
        if status in status_filters:
            query = query.filter_by(**status_filters[status])

        # 페이지네이션 적용 및 결과 반환
        return paginate_without_count(query, page=page, per_page=per_page)

    def list_notices_by_creator(self, creator_id: str, page: int = 1, per_page: int = 10) -> SimplePage:
        """생성자별 공지사항 목록 조회"""
        query = self.session.query(Notice).filter_by(creator_id=creator_id).order_by(Notice.created_at.desc())
        return paginate_without_count(query, page=page, per_page=per_page)