from typing import Optional

from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.repositories.base_repository import BaseRepository
from app.utils.simple_paging import paginate_without_count, SimplePage


class UserRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_id(self, id: str) -> Optional[User]:
        """ID로 사용자 조회"""
        return self.session.query(User).filter_by(id=id).first()

    def get_by_userid(self, userid: str) -> Optional[User]:
        """사용자 아이디로 사용자 조회"""
        return self.session.query(User).filter_by(userid=userid).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        return self.session.query(User).filter_by(email=email).first()

    def list_users(self, page: int = 1, per_page: int = 100) -> SimplePage:
        """사용자 목록 조회"""
        query = self.session.query(User).order_by(User.created_at.desc())
        return paginate_without_count(query, page=page, per_page=per_page)
