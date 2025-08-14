from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models.virtual_balance import VirtualBalance, VirtualBalanceHistory
from app.db.repositories.base_repository import BaseRepository


class VirtualBalanceRepository(BaseRepository):
    """가상 거래 잔고 레포지토리"""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def get_by_user_id(self, user_id: str) -> Optional[VirtualBalance]:
        """사용자 ID로 가상 잔고 조회"""
        return self.session.query(VirtualBalance).filter(
            VirtualBalance.user_id == user_id
        ).first()
    
    def create_user_balance(self, user_id: str, initial_cash: Decimal = Decimal('1000000')) -> VirtualBalance:
        """새 사용자의 가상 잔고 생성"""
        virtual_balance = VirtualBalance(
            user_id=user_id,
            cash_balance=initial_cash,
            available_cash=initial_cash,
            invested_amount=Decimal('0'),
            total_buy_amount=Decimal('0'),
            total_sell_amount=Decimal('0'),
            total_commission=Decimal('0'),
            total_tax=Decimal('0')
        )
        
        self.session.add(virtual_balance)
        self.session.flush()
        
        # 초기 잔고 생성 이력 추가
        self._add_balance_history(
            virtual_balance_id=virtual_balance.id,
            previous_cash=Decimal('0'),
            new_cash=initial_cash,
            change_amount=initial_cash,
            change_type='INITIAL_DEPOSIT',
            description='초기 가상 거래 잔고 생성'
        )
        
        return virtual_balance
    
    def deposit_cash(self, user_id: str, amount: Decimal, description: str = None) -> VirtualBalance:
        """현금 입금"""
        if amount is None or amount <= 0:
            raise ValueError("입금 금액은 0보다 커야 합니다.")
        virtual_balance = self.get_by_user_id(user_id)
        if not virtual_balance:
            # 잔고가 없으면 새로 생성
            virtual_balance = self.create_user_balance(user_id, amount)
            return virtual_balance
        
        previous_cash = virtual_balance.cash_balance
        virtual_balance.cash_balance += amount
        virtual_balance.available_cash += amount
        virtual_balance.last_updated_at = datetime.now()
        
        # 이력 추가
        self._add_balance_history(
            virtual_balance_id=virtual_balance.id,
            previous_cash=previous_cash,
            new_cash=virtual_balance.cash_balance,
            change_amount=amount,
            change_type='DEPOSIT',
            description=description or '현금 입금'
        )
        
        return virtual_balance
    
    def withdraw_cash(self, user_id: str, amount: Decimal, description: str = None) -> VirtualBalance:
        """현금 출금"""
        if amount is None or amount <= 0:
            raise ValueError("출금 금액은 0보다 커야 합니다.")
        virtual_balance = self.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("Virtual balance not found")
        
        if virtual_balance.available_cash < amount:
            raise ValueError("잔액이 충분 하지 않습니다.")
        
        previous_cash = virtual_balance.cash_balance
        virtual_balance.cash_balance -= amount
        virtual_balance.available_cash -= amount
        virtual_balance.last_updated_at = datetime.now()
        
        # 이력 추가
        self._add_balance_history(
            virtual_balance_id=virtual_balance.id,
            previous_cash=previous_cash,
            new_cash=virtual_balance.cash_balance,
            change_amount=-amount,
            change_type='WITHDRAW',
            description=description or '현금 출금'
        )
        
        return virtual_balance
    
    def update_balance_for_trade(
        self, 
        user_id: str, 
        cash_change: Decimal, 
        invested_change: Decimal,
        order_id: str = None,
        description: str = None
    ) -> VirtualBalance:
        """거래에 따른 잔고 업데이트"""
        virtual_balance = self.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("Virtual balance not found")
        
        previous_cash = virtual_balance.cash_balance
        virtual_balance.cash_balance += cash_change
        virtual_balance.available_cash += cash_change
        virtual_balance.invested_amount += invested_change
        virtual_balance.last_updated_at = datetime.now()
        
        # 매수/매도 금액 업데이트
        if cash_change < 0:  # 매수 (현금 감소)
            virtual_balance.total_buy_amount += abs(cash_change)
        else:  # 매도 (현금 증가)
            virtual_balance.total_sell_amount += cash_change
        
        # 이력 추가
        change_type = 'BUY' if cash_change < 0 else 'SELL'
        self._add_balance_history(
            virtual_balance_id=virtual_balance.id,
            previous_cash=previous_cash,
            new_cash=virtual_balance.cash_balance,
            change_amount=cash_change,
            change_type=change_type,
            related_order_id=order_id,
            description=description or f'{change_type} 거래'
        )
        
        return virtual_balance
    
    def get_balance_history(self, user_id: str, limit: int = 100) -> List[VirtualBalanceHistory]:
        """잔고 변동 이력 조회"""
        virtual_balance = self.get_by_user_id(user_id)
        if not virtual_balance:
            return []
        
        return self.session.query(VirtualBalanceHistory).filter(
            VirtualBalanceHistory.virtual_balance_id == virtual_balance.id
        ).order_by(VirtualBalanceHistory.created_at.desc()).limit(limit).all()
    
    def _add_balance_history(
        self,
        virtual_balance_id: str,
        previous_cash: Decimal,
        new_cash: Decimal,
        change_amount: Decimal,
        change_type: str,
        related_order_id: str = None,
        description: str = None
    ):
        """잔고 변동 이력 추가"""
        history = VirtualBalanceHistory(
            virtual_balance_id=virtual_balance_id,
            previous_cash_balance=previous_cash,
            new_cash_balance=new_cash,
            change_amount=change_amount,
            change_type=change_type,
            related_order_id=related_order_id,
            description=description
        )
        
        self.session.add(history)