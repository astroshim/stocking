from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timedelta
import calendar

from app.db.repositories.transaction_repository import TransactionRepository, TradingStatisticsRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.models.transaction import Transaction, TransactionType
from app.utils.simple_paging import SimplePage


class TransactionService:
    """거래 내역 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.transaction_repo = TransactionRepository(db)
        self.trading_stats_repo = TradingStatisticsRepository(db)
        self.virtual_balance_repo = VirtualBalanceRepository(db)
        self.portfolio_repo = PortfolioRepository(db)

    def create_transaction_from_order(
        self,
        user_id: str,
        order_id: str,
        stock_id: str,
        transaction_type: TransactionType,
        quantity: int,
        price: Decimal,
        commission: Decimal,
        tax: Decimal,
        description: Optional[str] = None
    ) -> Transaction:
        """주문에서 거래 내역 생성"""
        # 가상 잔고 조회
        virtual_balance = self.virtual_balance_repo.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        # 거래 금액 계산
        amount = quantity * price
        
        # 거래 전 잔고
        cash_balance_before = virtual_balance.cash_balance
        
        # 거래 후 잔고 계산
        if transaction_type == TransactionType.BUY:
            cash_balance_after = cash_balance_before - amount - commission - tax
        else:  # SELL
            cash_balance_after = cash_balance_before + amount - commission - tax
        
        # 거래 내역 생성
        transaction = self.transaction_repo.create_transaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            stock_id=stock_id,
            order_id=order_id,
            quantity=quantity,
            price=price,
            commission=commission,
            tax=tax,
            cash_balance_before=cash_balance_before,
            cash_balance_after=cash_balance_after,
            description=description or f"{transaction_type.value} {quantity}주 @ {price}"
        )
        
        return transaction

    def create_deposit_transaction(
        self,
        user_id: str,
        amount: Decimal,
        description: Optional[str] = None
    ) -> Transaction:
        """입금 거래 내역 생성"""
        virtual_balance = self.virtual_balance_repo.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        cash_balance_before = virtual_balance.cash_balance
        cash_balance_after = cash_balance_before + amount
        
        return self.transaction_repo.create_transaction(
            user_id=user_id,
            transaction_type=TransactionType.DEPOSIT,
            amount=amount,
            cash_balance_before=cash_balance_before,
            cash_balance_after=cash_balance_after,
            description=description or f"가상 잔고 입금: {amount}"
        )

    def create_withdraw_transaction(
        self,
        user_id: str,
        amount: Decimal,
        description: Optional[str] = None
    ) -> Transaction:
        """출금 거래 내역 생성"""
        virtual_balance = self.virtual_balance_repo.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        if virtual_balance.cash_balance < amount:
            raise ValueError("출금 가능한 잔고가 부족합니다")
        
        cash_balance_before = virtual_balance.cash_balance
        cash_balance_after = cash_balance_before - amount
        
        return self.transaction_repo.create_transaction(
            user_id=user_id,
            transaction_type=TransactionType.WITHDRAW,
            amount=amount,
            cash_balance_before=cash_balance_before,
            cash_balance_after=cash_balance_after,
            description=description or f"가상 잔고 출금: {amount}"
        )

    def get_transactions(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        transaction_type: Optional[TransactionType] = None,
        stock_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> SimplePage:
        """거래 내역 조회"""
        offset = (page - 1) * size
        
        transactions = self.transaction_repo.get_by_user_id(
            user_id=user_id,
            offset=offset,
            limit=size,
            transaction_type=transaction_type,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )
        
        total_count = self.transaction_repo.count_by_user_id(
            user_id=user_id,
            transaction_type=transaction_type,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # 거래 내역 데이터 변환
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'transaction_type': transaction.transaction_type.value,
                'stock_id': transaction.stock_id,
                'stock_name': f"주식 {transaction.stock_id}" if transaction.stock_id else None,
                'quantity': transaction.quantity,
                'price': float(transaction.price) if transaction.price else None,
                'amount': float(transaction.amount),
                'commission': float(transaction.commission),
                'tax': float(transaction.tax),
                'net_amount': float(transaction.net_amount),
                'cash_balance_before': float(transaction.cash_balance_before),
                'cash_balance_after': float(transaction.cash_balance_after),
                'transaction_date': transaction.transaction_date.isoformat(),
                'description': transaction.description,
                'reference_number': transaction.reference_number
            })
        
        return SimplePage(
            items=transaction_data,
            page=page,
            per_page=size,
            has_next=offset + size < total_count
        )

    def get_transaction_by_id(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
        """특정 거래 내역 조회"""
        transaction = self.transaction_repo.get_by_id_and_user(transaction_id, user_id)
        
        if not transaction:
            return None
        
        return {
            'id': transaction.id,
            'transaction_type': transaction.transaction_type.value,
            'stock_id': transaction.stock_id,
            'stock_name': f"주식 {transaction.stock_id}" if transaction.stock_id else None,
            'order_id': transaction.order_id,
            'quantity': transaction.quantity,
            'price': float(transaction.price) if transaction.price else None,
            'amount': float(transaction.amount),
            'commission': float(transaction.commission),
            'tax': float(transaction.tax),
            'net_amount': float(transaction.net_amount),
            'cash_balance_before': float(transaction.cash_balance_before),
            'cash_balance_after': float(transaction.cash_balance_after),
            'transaction_date': transaction.transaction_date.isoformat(),
            'settlement_date': transaction.settlement_date.isoformat() if transaction.settlement_date else None,
            'description': transaction.description,
            'reference_number': transaction.reference_number,
            'is_simulated': transaction.is_simulated,
            'created_at': transaction.created_at.isoformat()
        }

    def get_trading_statistics(
        self,
        user_id: str,
        period_type: str = "monthly",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """거래 통계 조회"""
        # 실시간 통계 계산 (실제로는 배치로 미리 계산된 통계를 조회)
        
        if period_type == "monthly":
            return self._get_monthly_statistics(user_id, start_date, end_date)
        elif period_type == "yearly":
            return self._get_yearly_statistics(user_id, start_date, end_date)
        else:
            # 기본적으로 거래 요약 반환
            summary = self.transaction_repo.get_trading_summary(user_id, 30)
            return [summary]

    def _get_monthly_statistics(self, user_id: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict[str, Any]]:
        """월별 통계"""
        year = end_date.year if end_date else datetime.now().year
        return self.transaction_repo.get_monthly_summary(user_id, year)

    def _get_yearly_statistics(self, user_id: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict[str, Any]]:
        """연별 통계"""
        # 간단한 연별 통계 구현
        current_year = datetime.now().year
        years = range(current_year - 4, current_year + 1)  # 최근 5년
        
        yearly_stats = []
        for year in years:
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)
            
            # 해당 연도 거래 요약
            transactions = self.transaction_repo.get_by_user_id(
                user_id=user_id,
                start_date=year_start,
                end_date=year_end
            )
            
            buy_amount = sum(t.amount for t in transactions if t.transaction_type == TransactionType.BUY)
            sell_amount = sum(t.amount for t in transactions if t.transaction_type == TransactionType.SELL)
            total_commission = sum(t.commission for t in transactions)
            total_tax = sum(t.tax for t in transactions)
            
            yearly_stats.append({
                'year': year,
                'buy_amount': float(buy_amount),
                'sell_amount': float(sell_amount),
                'net_amount': float(sell_amount - buy_amount),
                'total_commission': float(total_commission),
                'total_tax': float(total_tax),
                'transaction_count': len(transactions)
            })
        
        return yearly_stats

    def get_trading_performance(self, user_id: str, period: str = "1Y") -> Dict[str, Any]:
        """거래 성과 분석"""
        # 기간 계산
        end_date = datetime.now()
        if period == "1M":
            start_date = end_date - timedelta(days=30)
        elif period == "3M":
            start_date = end_date - timedelta(days=90)
        elif period == "6M":
            start_date = end_date - timedelta(days=180)
        elif period == "1Y":
            start_date = end_date - timedelta(days=365)
        else:  # ALL
            start_date = datetime(2020, 1, 1)  # 임의의 과거 날짜
        
        # 거래 요약
        summary = self.transaction_repo.get_trading_summary(user_id, (end_date - start_date).days)
        
        # 포트폴리오 요약
        portfolio_summary = self.portfolio_repo.get_portfolio_summary(user_id)
        
        # 성과 지표 계산 (간단한 버전)
        total_invested = summary['total_buy_amount']
        total_return = summary['net_amount']
        total_return_rate = (total_return / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'period': period,
            'total_return': float(total_return),
            'total_return_rate': float(total_return_rate),
            'annualized_return': float(total_return_rate),  # 간단히 동일값 사용
            'volatility': 15.0,  # 임시 값
            'sharpe_ratio': 1.2,  # 임시 값
            'max_drawdown': -10.0,  # 임시 값
            'win_rate': 60.0,  # 임시 값
            'profit_factor': 1.5,  # 임시 값
            'average_win': 50000.0,  # 임시 값
            'average_loss': -30000.0,  # 임시 값
            'total_trades': summary['total_transactions'],
            'total_invested': float(total_invested),
            'current_portfolio_value': float(portfolio_summary['total_current_value'])
        }

    def get_trading_dashboard(self, user_id: str) -> Dict[str, Any]:
        """거래 대시보드 데이터"""
        # 계좌 요약
        virtual_balance = self.virtual_balance_repo.get_by_user_id(user_id)
        portfolio_summary = self.portfolio_repo.get_portfolio_summary(user_id)
        
        account_summary = {
            'cash_balance': float(virtual_balance.cash_balance) if virtual_balance else 0.0,
            'invested_amount': float(portfolio_summary['total_invested_amount']),
            'total_asset_value': float(portfolio_summary['total_current_value']),
            'total_profit_loss': float(portfolio_summary['total_profit_loss']),
            'total_profit_loss_rate': float(portfolio_summary['total_profit_loss_rate'])
        }
        
        # 최근 거래내역 (5건)
        recent_transactions_page = self.get_transactions(user_id, page=1, size=5)
        recent_transactions = recent_transactions_page.items
        
        # 성과 지표
        performance_metrics = self.get_trading_performance(user_id, "1M")
        
        # 월별 성과 (최근 12개월)
        monthly_performance = self.transaction_repo.get_monthly_summary(user_id)
        
        # 상위 수익/손실 종목 (임시 구현)
        top_gainers = []
        top_losers = []
        
        return {
            'account_summary': account_summary,
            'recent_transactions': recent_transactions,
            'portfolio_summary': {
                'total_stocks': portfolio_summary['total_stocks'],
                'total_invested_amount': float(portfolio_summary['total_invested_amount']),
                'total_current_value': float(portfolio_summary['total_current_value']),
                'total_profit_loss': float(portfolio_summary['total_profit_loss']),
                'total_profit_loss_rate': float(portfolio_summary['total_profit_loss_rate'])
            },
            'performance_metrics': performance_metrics,
            'monthly_performance': monthly_performance,
            'top_gainers': top_gainers,
            'top_losers': top_losers
        }
