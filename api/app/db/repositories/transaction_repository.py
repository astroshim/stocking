from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func, extract
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.db.repositories.base_repository import BaseRepository
from app.db.models.transaction import Transaction, TransactionType, TradingStatistics


class TransactionRepository(BaseRepository):
    """거래 내역 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create_transaction(
        self,
        user_id: str,
        transaction_type: TransactionType,
        amount: Decimal,
        stock_id: Optional[str] = None,
        order_id: Optional[str] = None,
        quantity: Optional[int] = None,
        price: Optional[Decimal] = None,
        commission: Decimal = Decimal('0'),
        tax: Decimal = Decimal('0'),
        cash_balance_before: Decimal = Decimal('0'),
        cash_balance_after: Decimal = Decimal('0'),
        description: Optional[str] = None,
        realized_profit_loss: Optional[Decimal] = None,
        krw_realized_profit_loss: Optional[Decimal] = None,
        industry_code: Optional[str] = None,
        industry_display: Optional[str] = None
    ) -> Transaction:
        """거래 내역 생성"""
        net_amount = amount - commission - tax
        
        transaction = Transaction(
            user_id=user_id,
            stock_id=stock_id,
            order_id=order_id,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            amount=amount,
            commission=commission,
            tax=tax,
            net_amount=net_amount,
            cash_balance_before=cash_balance_before,
            cash_balance_after=cash_balance_after,
            description=description,
            transaction_date=datetime.now(),
            is_simulated=True,
            realized_profit_loss=realized_profit_loss,
            krw_realized_profit_loss=krw_realized_profit_loss,
            industry_code=industry_code,
            industry_display=industry_display
        )
        
        self.session.add(transaction)
        self.session.flush()
        return transaction

    def get_by_user_id(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
        transaction_type: Optional[TransactionType] = None,
        stock_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Transaction]:
        """사용자 거래 내역 조회 (N+1 쿼리 방지를 위해 order를 eager loading)"""
        query = self.session.query(Transaction).options(joinedload(Transaction.order)).filter(Transaction.user_id == user_id)
        
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        if stock_id:
            query = query.filter(Transaction.stock_id == stock_id)
        
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)
        
        return query.order_by(desc(Transaction.transaction_date)).offset(offset).limit(limit).all()

    def count_by_user_id(
        self,
        user_id: str,
        transaction_type: Optional[TransactionType] = None,
        stock_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """사용자 거래 내역 개수 조회"""
        query = self.session.query(Transaction).filter(Transaction.user_id == user_id)
        
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        if stock_id:
            query = query.filter(Transaction.stock_id == stock_id)
        
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)
        
        return query.count()

    def get_by_id_and_user(self, transaction_id: str, user_id: str) -> Optional[Transaction]:
        """특정 거래 내역 조회 (N+1 쿼리 방지를 위해 order를 eager loading)"""
        return self.session.query(Transaction).options(joinedload(Transaction.order)).filter(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            )
        ).first()

    def get_realized_cost_krw_by_stock(self, user_id: str, stock_id: str) -> Decimal:
        """특정 종목의 누적 실현원가(KRW)를 추정 계산합니다.
        SELL 거래의 총액 - 원화 실현손익 = 원가 합계 (수수료/세금 포함 기준).
        """
        # SELL 총액 (amount, KRW 기준 저장됨)
        sell_amount = self.session.query(func.sum(Transaction.amount)).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.stock_id == stock_id,
                Transaction.transaction_type == TransactionType.SELL
            )
        ).scalar() or Decimal('0')

        # SELL의 KRW 실현손익 합계
        realized_sum = self.session.query(func.sum(Transaction.krw_realized_profit_loss)).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.stock_id == stock_id,
                Transaction.transaction_type == TransactionType.SELL
            )
        ).scalar() or Decimal('0')

        return sell_amount - realized_sum


class TradingStatisticsRepository(BaseRepository):
    """거래 통계 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create_or_update_statistics(
        self,
        user_id: str,
        period_type: str,
        period_start: datetime,
        period_end: datetime,
        statistics_data: Dict[str, Any]
    ) -> TradingStatistics:
        """거래 통계 생성 또는 업데이트"""
        existing = self.session.query(TradingStatistics).filter(
            and_(
                TradingStatistics.user_id == user_id,
                TradingStatistics.period_type == period_type,
                TradingStatistics.period_start == period_start
            )
        ).first()
        
        if existing:
            # 기존 통계 업데이트
            for key, value in statistics_data.items():
                setattr(existing, key, value)
            return existing
        else:
            # 새 통계 생성
            stats = TradingStatistics(
                user_id=user_id,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                **statistics_data
            )
            self.session.add(stats)
            self.session.flush()
            return stats

    def get_by_user_and_period(
        self,
        user_id: str,
        period_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[TradingStatistics]:
        """사용자별 기간별 통계 조회"""
        query = self.session.query(TradingStatistics).filter(
            and_(
                TradingStatistics.user_id == user_id,
                TradingStatistics.period_type == period_type
            )
        )
        
        if start_date:
            query = query.filter(TradingStatistics.period_start >= start_date)
        
        if end_date:
            query = query.filter(TradingStatistics.period_end <= end_date)
        
        return query.order_by(desc(TradingStatistics.period_start)).all()
