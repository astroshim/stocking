from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime

from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.models.portfolio import Portfolio
from app.db.models.transaction import Transaction, TransactionType
from sqlalchemy import func
from app.db.models.virtual_balance import VirtualBalance, VirtualBalanceHistory
from app.services.payment_service import PaymentService
from app.api.v1.schemas.virtual_balance_schema import BalanceUpdateRequest


class BalanceService:
    """가상 잔고 관리 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
        self.virtual_balance_repo = VirtualBalanceRepository(db)
        self.payment_service = PaymentService(db)
        self.portfolio_repo = PortfolioRepository(db)
    
    def get_virtual_balance(self, user_id: str) -> Optional[VirtualBalance]:
        """
        사용자의 가상 거래 잔고를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            가상 잔고 정보
        """
        return self.payment_service.get_virtual_balance(user_id)
    
    def initialize_virtual_balance(
        self, 
        user_id: str, 
        initial_amount: Decimal = Decimal('1000000')
    ) -> VirtualBalance:
        """
        사용자의 가상 잔고를 초기화합니다.
        
        Args:
            user_id: 사용자 ID
            initial_amount: 초기 금액 (기본값: 1,000,000)
            
        Returns:
            생성된 가상 잔고 정보
        """
        return self.payment_service.initialize_virtual_balance(user_id, initial_amount)
    
    def deposit(
        self, 
        user_id: str, 
        amount: float, 
        description: Optional[str] = None
    ) -> VirtualBalance:
        """
        가상 거래 잔고에 입금합니다.
        
        Args:
            user_id: 사용자 ID
            amount: 입금 금액
            description: 입금 설명
            
        Returns:
            업데이트된 가상 잔고 정보
        """
        return self.payment_service.deposit_virtual_balance(
            user_id=user_id,
            amount=Decimal(str(amount)),
            description=description or "가상 거래 잔고 입금"
        )
    
    def withdraw(
        self, 
        user_id: str, 
        amount: float, 
        description: Optional[str] = None
    ) -> VirtualBalance:
        """
        가상 거래 잔고에서 출금합니다.
        
        Args:
            user_id: 사용자 ID
            amount: 출금 금액  
            description: 출금 설명
            
        Returns:
            업데이트된 가상 잔고 정보
        """
        return self.payment_service.withdraw_virtual_balance(
            user_id=user_id,
            amount=Decimal(str(amount)),
            description=description or "가상 거래 잔고 출금"
        )
    
    def update_balance(
        self, 
        user_id: str, 
        balance_data: BalanceUpdateRequest
    ) -> Dict[str, Any]:
        """
        잔고 정보를 업데이트합니다 (메모 등 메타데이터).
        
        Args:
            user_id: 사용자 ID
            balance_data: 업데이트할 잔고 데이터
            
        Returns:
            업데이트 결과
        """
        try:
            # 현재는 간단한 업데이트만 지원
            # 향후 메모 업데이트, 알림 설정 등을 추가할 수 있음
            return {
                "status": "success",
                "message": "잔고 업데이트가 완료되었습니다.",
                "updated_at": datetime.now()
            }
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_balance_history(
        self,
        user_id: str,
        page: int = 1,
        size: int = 50,
        change_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        잔고 변동 이력을 조회합니다.
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            size: 페이지 크기
            change_type: 변경 유형 필터
            start_date: 시작일
            end_date: 종료일
            
        Returns:
            잔고 변동 이력 목록
        """
        try:
            # VirtualBalanceHistory와 VirtualBalance를 조인하여 user_id로 필터링
            from app.db.models.virtual_balance import VirtualBalance
            
            query = self.db.query(VirtualBalanceHistory).join(
                VirtualBalance, VirtualBalanceHistory.virtual_balance_id == VirtualBalance.id
            ).filter(
                VirtualBalance.user_id == user_id
            )
            
            # 변경 유형 필터링
            if change_type:
                query = query.filter(VirtualBalanceHistory.change_type == change_type)
            
            # 날짜 필터링
            if start_date:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(VirtualBalanceHistory.created_at >= start_datetime)
            
            if end_date:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(VirtualBalanceHistory.created_at <= end_datetime)
            
            # 페이징 처리
            offset = (page - 1) * size
            history_records = query.order_by(
                VirtualBalanceHistory.created_at.desc()
            ).offset(offset).limit(size).all()
            
            # 딕셔너리로 변환 (실제 모델 필드명에 맞춰 수정)
            history_data = []
            for record in history_records:
                history_data.append({
                    'id': record.id,
                    'virtual_balance_id': record.virtual_balance_id,
                    'change_type': record.change_type,
                    'change_amount': float(record.change_amount),
                    'previous_cash_balance': float(record.previous_cash_balance),
                    'new_cash_balance': float(record.new_cash_balance),
                    'related_order_id': record.related_order_id,
                    'description': record.description,
                    'created_at': record.created_at.isoformat() if record.created_at else None
                })
            
            return history_data
            
        except Exception as e:
            raise e
    
    def get_balance_summary(self, user_id: str) -> Dict[str, Any]:
        """
        사용자의 잔고 요약 정보를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            잔고 요약 정보
        """
        virtual_balance = self.get_virtual_balance(user_id)

        if not virtual_balance:
            return {
                'total_balance': 0,
                'available_cash': 0,
                'invested_amount': 0,
                'total_profit_loss': 0,
                'total_commission': 0,
                'total_tax': 0,
                'total_buy_amount': 0,
                'total_sell_amount': 0
            }

        # invested_amount는 VirtualBalance에서 직접 가져오기 (매수/매도 시 업데이트되는 값)
        invested_amount = virtual_balance.invested_amount or Decimal('0')

        # 거래 기준 총계 (Transaction에서 집계)
        buy_amount = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.BUY
        ).scalar() or Decimal('0')

        sell_amount = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL
        ).scalar() or Decimal('0')

        total_commission = self.db.query(func.sum(Transaction.commission)).filter(
            Transaction.user_id == user_id
        ).scalar() or Decimal('0')

        total_tax = self.db.query(func.sum(Transaction.tax)).filter(
            Transaction.user_id == user_id
        ).scalar() or Decimal('0')

        total_profit_loss = float(sell_amount - buy_amount - total_commission - total_tax)

        return {
            'total_balance': float(virtual_balance.cash_balance),
            'available_cash': float(virtual_balance.available_cash),
            'invested_amount': float(invested_amount),
            'total_profit_loss': total_profit_loss,
            'total_commission': float(total_commission),
            'total_tax': float(total_tax),
            'total_buy_amount': float(buy_amount),
            'total_sell_amount': float(sell_amount),
            'last_trade_date': virtual_balance.last_trade_date.isoformat() if virtual_balance.last_trade_date else None,
            'last_updated_at': virtual_balance.last_updated_at.isoformat() if virtual_balance.last_updated_at else None
        }
