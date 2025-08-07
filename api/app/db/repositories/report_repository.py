import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.db.repositories.base_repository import BaseRepository
from app.db.models.report import Report
from app.utils.simple_paging import paginate_without_count, SimplePage


class ReportRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_id(self, report_id: str) -> Optional[Report]:
        """ID로 신고 조회"""
        return self.session.get(Report, report_id)

    def list_reports(self, filters: Dict[str, Any] = None) -> SimplePage:
        """
        신고 목록을 다양한 필터 조건으로 조회

        Parameters:
            filters (dict): 필터 조건을 담은 딕셔너리
                - user_id (str, optional): 신고자 ID로 필터링
                - status (str, optional): 처리 상태로 필터링
                - reportable_type (str, optional): 신고 대상 유형으로 필터링
                - reportable_id (str, optional): 신고 대상 ID로 필터링
                - handled_by (str, optional): 처리자 ID로 필터링
                - start_date (datetime, optional): 이 날짜 이후 신고만 조회
                - end_date (datetime, optional): 이 날짜 이전 신고만 조회
                - sort_by (str, optional): 정렬 기준 필드 (기본값: 'created_at')
                - sort_order (str, optional): 정렬 방향 ('asc' 또는 'desc', 기본값: 'desc')
                - page (int, optional): 페이지 번호
                - per_page (int, optional): 페이지당 항목 수

        Returns:
            List[Report]: 필터링된 신고 목록
        """
        # 기본 쿼리 생성
        query = self.session.query(Report)

        # filters 파라미터가 None이면 빈 딕셔너리로 초기화
        if filters is None:
            filters = {}

        # 각 필터 조건 적용
        if filters.get('user_id'):
            query = query.filter_by(user_id=filters['user_id'])

        if filters.get('status'):
            query = query.filter_by(status=filters['status'])

        if filters.get('reportable_type'):
            query = query.filter_by(reportable_type=filters['reportable_type'])

        if filters.get('reportable_id'):
            query = query.filter_by(reportable_id=filters['reportable_id'])

        if filters.get('handled_by'):
            query = query.filter_by(handled_by=filters['handled_by'])

        # 날짜 범위 필터링 (선택 사항)
        if filters.get('start_date'):
            query = query.filter(Report.created_at >= filters['start_date'])

        if filters.get('end_date'):
            query = query.filter(Report.created_at <= filters['end_date'])

        # 정렬 (기본값: 생성일 기준 내림차순)
        sort_by = filters.get('sort_by', 'created_at')
        sort_order = filters.get('sort_order', 'desc')

        if hasattr(Report, sort_by):
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(getattr(Report, sort_by)))
            else:
                query = query.order_by(asc(getattr(Report, sort_by)))

        page = 1
        per_page = 10
        # 페이지네이션 처리 (선택 사항)
        if filters.get('page') and filters.get('per_page'):
            page = int(filters['page'])
            per_page = int(filters['per_page'])

            logging.debug(f"query : {query}")
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)

        logging.debug(f"query : {query}")
        # 결과 반환
        return paginate_without_count(query, page=page, per_page=per_page)
