import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.db.repositories.base_repository import BaseRepository
from app.db.models.comment import Comment
from app.utils.simple_paging import paginate_without_count, SimplePage


class CommentRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_id(self, comment_id: str) -> Optional[Comment]:
        """ID로 신고 조회"""
        return self.session.get(Comment, comment_id)

    def list_comments(self, filters=None):
        """
        필터 기준에 따라 코멘트 목록을 조회합니다.

        Args:
            filters (dict, optional): 필터링 조건
                - commentable_type (str, optional): 코멘트 대상 타입
                - commentable_id (str, optional): 코멘트 대상 ID
                - parent_id (str, optional): 부모 코멘트 ID (대댓글 필터링)
                - include_replies (bool, optional): 대댓글 포함 여부
                - page (int, optional): 페이지 번호
                - per_page (int, optional): 페이지당 항목 수
                # - sort_by (str, optional): 정렬 기준 필드
                # - sort_order (str, optional): 정렬 방향 ('asc' 또는 'desc')

        Returns:
            Pagination: 페이징 처리된 코멘트 목록
        """
        # 필터가 없으면 빈 딕셔너리로 초기화
        if filters is None:
            filters = {}

        # 기본 쿼리 생성
        query = self.session.query(Comment)

        # 필터 조건 적용
        if filters.get('commentable_type'):
            query = query.filter(Comment.commentable_type == filters['commentable_type'])

        if filters.get('commentable_id'):
            query = query.filter(Comment.commentable_id == filters['commentable_id'])

        # 부모 코멘트 ID로 필터링
        if filters.get('parent_id'):
            query = query.filter(Comment.ancestry == filters['parent_id'])
        elif not filters.get('include_replies', False):
            # 대댓글을 포함하지 않는 경우, 최상위 코멘트만 조회 (ancestry가 None인 코멘트)
            query = query.filter(Comment.ancestry.is_(None))

        # 정렬 (기본값: ancestry_depth 기준 오름차순, 같은 깊이는 생성일 기준 정렬)
        sort_by = filters.get('sort_by', 'ancestry_depth')
        sort_order = filters.get('sort_order', 'asc')  # 깊이는 일반적으로 오름차순이 적절합니다

        if hasattr(Comment, sort_by):
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(getattr(Comment, sort_by)))
                # 같은 깊이의 코멘트는 생성 일자 순으로 정렬
                if sort_by == 'ancestry_depth':
                    query = query.order_by(desc(Comment.ancestry_depth), asc(Comment.created_at))
            else:
                # 같은 깊이의 코멘트는 생성 일자 순으로 정렬
                if sort_by == 'ancestry_depth':
                    query = query.order_by(asc(Comment.ancestry_depth), asc(Comment.created_at))
                else:
                    query = query.order_by(asc(getattr(Comment, sort_by)))

        # 페이지네이션 처리
        page = int(filters.get('page', 1))
        per_page = int(filters.get('per_page', 10))

        return paginate_without_count(query, page=page, per_page=per_page)
