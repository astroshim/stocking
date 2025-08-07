import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.db.models.notice import Notice
from app.db.repositories.notice_repository import NoticeRepository
from app.utils.transaction_manager import TransactionManager


class NoticeService:
    def __init__(self, notice_repository: NoticeRepository):
        self.repository = notice_repository

    def create_notice(self, user_id: str, notice_data: Dict[str, Any]) -> Notice:
        """공지사항 생성 서비스"""
        with TransactionManager.transaction(self.repository.session):
            notice = Notice(
                creator_id=user_id,
                title=notice_data['title'],
                content=notice_data['content'],
                is_active=notice_data.get('is_active', True),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            logging.debug(f"Creating notice: {notice_data}, user_id: {user_id}")
            self.repository.add(notice)
            return notice

    def get_notice_by_id(self, notice_id: str) -> Optional[Notice]:
        """ID로 공지사항 조회"""
        return self.repository.get_by_id(notice_id)

    def update_notice(self, notice_id: str, notice_data: Dict[str, Any]) -> Optional[Notice]:
        """공지사항 정보 업데이트"""
        with TransactionManager.transaction(self.repository.session):
            notice = self.repository.get_by_id(notice_id)
            if not notice:
                return None

            # 필드 업데이트
            for key, value in notice_data.items():
                if hasattr(notice, key):
                    setattr(notice, key, value)

            notice.updated_at = datetime.now()
            return notice

    def delete_notice(self, user_id: str, notice_id: str) -> bool:
        """공지사항 삭제"""
        with TransactionManager.transaction(self.repository.session):
            notice = self.repository.get_by_id_and_user(user_id, notice_id)
            if notice:
                self.repository.delete(notice)
                return True
            return False

    def list_notices(self, status: str = 'all', page: int = 1, per_page: int = 10):
        """공지사항 목록 조회"""
        return self.repository.list_notices(status, page, per_page)

    def list_notices_by_creator(self, creator_id: str, page: int = 1, per_page: int = 10):
        """생성자별 공지사항 목록 조회"""
        return self.repository.list_notices_by_creator(creator_id, page, per_page)