import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.db.models import ReportStatusHistory
from app.db.models.report import Report
from app.db.repositories.report_repository import ReportRepository
from app.utils.argument_helper import get_filters
from app.utils.transaction_manager import TransactionManager


class ReportService:
    def __init__(self, repository: ReportRepository):
        self.repository = repository
        self.optional_params = ['status',
                                'user_id',
                                'reportable_type',
                                'reportable_id',
                                'handled_by',
                                'start_date',
                                'end_date',
                                'sort_by',
                                'sort_order',
                                'page',
                                'per_page']

    def create_report(self, report_data: Dict[str, Any]) -> Report:
        """새로운 신고 생성"""
        with TransactionManager.transaction(self.repository.session):
            report = Report(
                user_id=report_data['user_id'],
                reportable_type=report_data['reportable_type'],
                reportable_id=report_data['reportable_id'],
                reason=report_data['reason'],
                description=report_data.get('description', ''),
                status=report_data.get('status', 'pending'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.repository.add(report)
            return report

    def update_status(self, data: Dict[str, Any]) -> Optional[Report]:
        """신고 상태 업데이트"""
        with TransactionManager.transaction(self.repository.session):
            report_id = data.get("id")
            report = self.repository.get_by_id(report_id)
            if not report:
                logging.error(f"신고 ID를 찾을 수 없음: {report_id}")
                return None

            # 인증 상태 확인
            if report.status not in ['pending', 'in_progress', 'resolved']:
                raise ValueError("ready 만 인증 상태를 변경할 수 있습니다.")

            # 인증 상태 확인
            if report.status == data['status']:
                raise ValueError("같은 상태로 변경할 수 없습니다.")

            # 현재 시각 기준 처리
            handled_at = datetime.now()
            # reports 테이블의 상태 업데이트
            report.status = data['status']
            # report.resolution = data.get('resolution')
            report.handler_comment = data.get('handler_comment')
            report.handled_by = data['handled_by']
            report.handled_at = handled_at

            # 이력 테이블에 히스토리 남기기
            history = ReportStatusHistory(
                report_id=report_id,
                status=data['status'],
                # resolution=data.get('resolution'),
                handled_by=data['handled_by'],
                handler_comment=data.get('handler_comment'),
                handled_at=handled_at
            )
            self.repository.add(history)
            return report

    def get_by_id(self, report_id: str) -> Optional[Report]:
        """ID로 신고 조회"""
        return self.repository.get_by_id(report_id)

    def list_reports(self, args: dict = None):
        """필터 조건에 맞는 신고 목록 조회"""
        return self.repository.list_reports(get_filters(args, self.optional_params))
