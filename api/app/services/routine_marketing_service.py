from app.db.repositories.routine_marketing_repository import RoutineMarketingRepository
from app.db.models.routine_marketing import RoutineMarketing
from app.utils.transaction_manager import TransactionManager
from app.api.v1.schemas.routine_marketing_schema import CreateRoutineMarketing, ClientInfo
from app.utils.simple_paging import SimplePage
from typing import Optional


class RoutineMarketingService:
    def __init__(self, routine_marketing_repository: RoutineMarketingRepository):
        self.routine_marketing_repository = routine_marketing_repository

    def create_routine_marketing(self, routine_marketing_data: CreateRoutineMarketing, client_info: ClientInfo) -> RoutineMarketing:
        with TransactionManager.transaction(self.routine_marketing_repository.session):
            routine_marketing_obj = RoutineMarketing(
                **routine_marketing_data.model_dump(),
                **client_info.model_dump()
            )
            self.routine_marketing_repository.add(routine_marketing_obj)
            return routine_marketing_obj

    def get_routine_marketing_by_id(self, id: str) -> Optional[RoutineMarketing]:
        """ID로 루틴 마케팅 정보 조회"""
        return self.routine_marketing_repository.get_by_id(id)

    def list_routine_marketing(self, page: int = 1, per_page: int = 10) -> SimplePage:
        """루틴 마케팅 리스트 조회 (페이징 처리)"""
        return self.routine_marketing_repository.list_routine_marketing(page, per_page)

    def delete_routine_marketing(self, id: str) -> bool:
        """루틴 마케팅 정보 삭제"""
        with TransactionManager.transaction(self.routine_marketing_repository.session):
            return self.routine_marketing_repository.delete_by_id(id) 