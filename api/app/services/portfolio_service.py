from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.models.portfolio import VirtualBalance, VirtualBalanceHistory
from app.utils.transaction_manager import TransactionManager


class PortfolioService:
    """포트폴리오 관련 비즈니스 로직을 처리하는 서비스"""
    
    def __init__(self, virtual_balance_repository: VirtualBalanceRepository):
        self.virtual_balance_repository = virtual_balance_repository
        
    def get_virtual_balance(self, user_id: str) -> Optional[VirtualBalance]:
        """
        사용자의 가상 잔고를 조회합니다.
        가상 잔고가 없으면 기본값으로 생성합니다.
        """
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        
        # 가상잔고가 없으면 새로 생성 (지연 생성)
        if not virtual_balance:
            with TransactionManager.transaction(self.virtual_balance_repository.session):
                virtual_balance = self.virtual_balance_repository.create_user_balance(
                    user_id, Decimal('1000000')
                )
                logging.info(f"Virtual balance created for user {user_id}")
                
        return virtual_balance
    
    def update_virtual_balance(self, user_id: str, amount: Decimal, change_type: str, description: str = None) -> VirtualBalance:
        """
        가상 잔고를 업데이트합니다.
        
        Args:
            user_id: 사용자 ID
            amount: 변경 금액
            change_type: 변경 유형 (DEPOSIT, WITHDRAW만 허용)
            description: 변경 설명
            
        Returns:
            업데이트된 가상 잔고
            
        Raises:
            ValueError: 잘못된 변경 유형이거나 잔액이 부족한 경우
        """
        # 사용자가 직접 변경할 수 있는 유형만 허용
        allowed_types = ["DEPOSIT", "WITHDRAW"]
        change_type_upper = change_type.upper() if isinstance(change_type, str) else str(change_type).upper()
        
        if change_type_upper not in allowed_types:
            raise ValueError(f"사용자가 직접 변경할 수 없는 유형입니다: {change_type}. DEPOSIT(입금) 또는 WITHDRAW(출금)만 사용할 수 있습니다.")
        
        with TransactionManager.transaction(self.virtual_balance_repository.session):
            if change_type_upper == "DEPOSIT":
                updated_balance = self.virtual_balance_repository.deposit_cash(
                    user_id=user_id,
                    amount=amount,
                    description=description
                )
            elif change_type_upper == "WITHDRAW":
                updated_balance = self.virtual_balance_repository.withdraw_cash(
                    user_id=user_id,
                    amount=amount,
                    description=description
                )
            
            logging.info(f"Virtual balance updated for user {user_id}: {change_type} {amount}")
            return updated_balance
    
    def get_balance_history(
        self, 
        user_id: str,
        page: int = 1,
        size: int = 50,
        change_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[VirtualBalanceHistory]:
        """
        잔고 변동 이력을 조회합니다.
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            size: 페이지 크기
            change_type: 변경 유형 필터
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            
        Returns:
            잔고 변동 이력 리스트
            
        Raises:
            ValueError: 날짜 형식이 올바르지 않은 경우
        """
        # 사용자의 가상잔고 확인
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        if not virtual_balance:
            return []
        
        # 페이징 계산
        offset = (page - 1) * size
        
        # 기본 쿼리
        from app.db.models.portfolio import VirtualBalanceHistory
        query = self.virtual_balance_repository.session.query(VirtualBalanceHistory).filter(
            VirtualBalanceHistory.virtual_balance_id == virtual_balance.id
        )
        
        # 변경 유형 필터
        if change_type:
            query = query.filter(VirtualBalanceHistory.change_type == change_type.upper())
        
        # 날짜 필터 적용
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(VirtualBalanceHistory.created_at >= start_datetime)
            except ValueError:
                raise ValueError("시작일 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                # 하루 끝까지 포함하기 위해 23:59:59 추가
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                query = query.filter(VirtualBalanceHistory.created_at <= end_datetime)
            except ValueError:
                raise ValueError("종료일 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        # 최신순 정렬 및 페이징
        history_records = query.order_by(
            VirtualBalanceHistory.created_at.desc()
        ).offset(offset).limit(size).all()
        
        return history_records
    
    def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """
        포트폴리오 요약 정보를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            포트폴리오 요약 정보
        """
        virtual_balance = self.get_virtual_balance(user_id)
        
        # TODO: 실제 포트폴리오 데이터를 기반으로 계산
        summary = {
            "total_stocks": 0,
            "total_invested_amount": virtual_balance.invested_amount,
            "total_current_value": virtual_balance.total_portfolio_value,
            "total_profit_loss": virtual_balance.total_profit_loss,
            "total_profit_loss_rate": virtual_balance.total_profit_loss_rate
        }
        
        return summary
    
    def get_portfolio_analysis(self, user_id: str) -> Dict[str, Any]:
        """
        포트폴리오 분석 정보를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            포트폴리오 분석 정보
        """
        # TODO: 실제 포트폴리오 분석 로직 구현
        analysis = {
            "sector_allocation": [],
            "top_holdings": [],
            "performance_metrics": {},
            "risk_metrics": {}
        }
        
        return analysis
