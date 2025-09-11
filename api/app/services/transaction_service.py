from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

from app.db.repositories.transaction_repository import TransactionRepository, TradingStatisticsRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.models.transaction import Transaction, TransactionType
from app.utils.simple_paging import SimplePage
from app.db.models.order import Order
from app.utils.data_converters import DataConverters
import logging


class TransactionService:
    """거래 내역 서비스"""

    def __init__(
        self, 
        db: Session, 
        transaction_repository: TransactionRepository, 
        virtual_balance_repository: VirtualBalanceRepository,
        portfolio_repository: PortfolioRepository
    ):
        self.db = db
        self.transaction_repository = transaction_repository
        self.virtual_balance_repository = virtual_balance_repository
        self.portfolio_repository = portfolio_repository

    def create_transaction_from_order(
        self,
        order: Order,
        transaction_type: TransactionType,
        amount: Decimal,
        price: Decimal,
        quantity: Decimal,
        commission: Decimal = Decimal('0'),
        tax: Decimal = Decimal('0'),
        notes: Optional[str] = None,
        currency: Optional[str] = 'KRW',
        exchange_rate: Optional[Decimal] = None,
        krw_execution_amount: Optional[Decimal] = None,
        realized_profit_loss: Optional[Decimal] = None,
        krw_realized_profit_loss: Optional[Decimal] = None,
    ) -> Transaction:
        """주문에서 거래 내역 생성"""
        # 가상 잔고 조회
        virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        # 거래 금액 계산 (해외자산은 KRW 기준으로 기록)
        if currency and currency != 'KRW':
            rate = exchange_rate or Decimal('0')
            amount = krw_execution_amount if krw_execution_amount is not None else (amount * rate)
        else:
            amount = amount
        
        # 거래 전 잔고
        cash_balance_before = virtual_balance.cash_balance
        
        # 거래 후 잔고 계산
        if transaction_type == TransactionType.BUY:
            cash_balance_after = cash_balance_before - amount - commission - tax
        else:  # SELL
            cash_balance_after = cash_balance_before + amount - commission - tax
        
        # 거래 내역 생성
        # 설명 보강(해외자산 환율 표시)
        desc = notes or f"{transaction_type.value} {order.quantity}주 @ {order.order_price}"
        if currency and currency != 'KRW':
            if exchange_rate:
                desc = f"{desc} (환율: {exchange_rate} {currency}->KRW)"

        transaction = self.transaction_repository.create_transaction(
            user_id=order.user_id,
            transaction_type=transaction_type,
            amount=amount,
            stock_id=order.product_code,
            order_id=order.id,
            quantity=order.quantity,
            price=order.order_price,
            commission=commission,
            tax=tax,
            cash_balance_before=cash_balance_before,
            cash_balance_after=cash_balance_after,
            description=desc,
            realized_profit_loss=realized_profit_loss,
            krw_realized_profit_loss=krw_realized_profit_loss,
            industry_code=getattr(order, 'industry_code', None),
            industry_display=getattr(order, 'industry_display', None)
        )
        
        return transaction

    def create_deposit_transaction(
        self,
        user_id: str,
        amount: Decimal,
        description: Optional[str] = None
    ) -> Transaction:
        """입금 거래 내역 생성"""
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        cash_balance_before = virtual_balance.cash_balance
        cash_balance_after = cash_balance_before + amount
        
        return self.transaction_repository.create_transaction(
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
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        if not virtual_balance:
            raise ValueError("가상 잔고를 찾을 수 없습니다")
        
        if virtual_balance.cash_balance < amount:
            raise ValueError("출금 가능한 잔고가 부족합니다")
        
        cash_balance_before = virtual_balance.cash_balance
        cash_balance_after = cash_balance_before - amount
        
        return self.transaction_repository.create_transaction(
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
        
        transactions = self.transaction_repository.get_by_user_id(
            user_id=user_id,
            offset=offset,
            limit=size,
            transaction_type=transaction_type,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )
        
        total_count = self.transaction_repository.count_by_user_id(
            user_id=user_id,
            transaction_type=transaction_type,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # 거래 내역 데이터 변환 (스키마 필드 준수)
        transaction_data = [self._to_transaction_dict(t) for t in transactions]
        
        return SimplePage(items=transaction_data, page=page, per_page=size, has_next=offset + size < total_count)

    def get_transaction_by_id(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
        """특정 거래 내역 조회"""
        transaction = self.transaction_repository.get_by_id_and_user(transaction_id, user_id)
        
        if not transaction:
            return None
        
        return self._to_transaction_dict(transaction)

    # ===== 내부 헬퍼 =====
    def _to_order_brief(self, order: Optional[Order]) -> Optional[Dict[str, Any]]:
        if not order:
            return None
        return {
            'id': order.id,
            'product_code': getattr(order, 'product_code', None),
            'product_name': getattr(order, 'product_name', None),
            'market': getattr(order, 'market', None),
            'order_type': order.order_type.value if getattr(order, 'order_type', None) else None,
            'order_method': order.order_method.value if getattr(order, 'order_method', None) else None,
            'currency': getattr(order, 'currency', None),
            'exchange_rate': getattr(order, 'exchange_rate', None),
            'order_price': getattr(order, 'order_price', None),
            'krw_order_price': getattr(order, 'krw_order_price', None),
        }

    def _to_transaction_dict(self, transaction: Transaction) -> Dict[str, Any]:
        return {
            'id': transaction.id,
            'user_id': transaction.user_id,
            'order_id': transaction.order_id,
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
            'transaction_date': transaction.transaction_date,
            'settlement_date': transaction.settlement_date,
            'description': transaction.description,
            'reference_number': transaction.reference_number,
            'is_simulated': transaction.is_simulated,
            'created_at': transaction.created_at,
            'order': self._to_order_brief(transaction.order) if transaction.order else None,
            'realized_profit_loss': float(getattr(transaction, 'realized_profit_loss', 0)) if getattr(transaction, 'realized_profit_loss', None) is not None else None,
            'krw_realized_profit_loss': float(getattr(transaction, 'krw_realized_profit_loss', 0)) if getattr(transaction, 'krw_realized_profit_loss', None) is not None else None,
        }

    def _parse_period_dates(self, period_type: str, period_value: Optional[str] = None) -> tuple[datetime, datetime]:
        """
        기간 타입과 값을 파싱하여 시작일과 종료일을 반환합니다.
        
        Args:
            period_type: 기간 타입 (day/week/month/year/all)
            period_value: 기간 값 (예: 2024-09-10, 2024-10-2, 2024-09, 2024)
        
        Returns:
            tuple[datetime, datetime]: (시작일, 종료일)
        """
        if period_type == 'day':
            # 특정 날짜 (예: 2024-09-10)
            if not period_value:
                raise ValueError("day 타입은 period_value가 필요합니다 (형식: YYYY-MM-DD)")
            start_date = datetime.strptime(period_value, "%Y-%m-%d")
            end_date = start_date.replace(hour=23, minute=59, second=59)
            
        elif period_type == 'week':
            # 특정 주 (예: 2024-10-2 => 2024년 10월 2주)
            if not period_value:
                raise ValueError("week 타입은 period_value가 필요합니다 (형식: YYYY-MM-W)")
            try:
                parts = period_value.split('-')
                if len(parts) != 3:
                    raise ValueError("잘못된 주차 형식입니다. YYYY-MM-W 형식을 사용하세요")
                
                year = int(parts[0])
                month = int(parts[1])
                week_of_month = int(parts[2])
                
                if month < 1 or month > 12:
                    raise ValueError("월은 1-12 사이여야 합니다")
                if week_of_month < 1 or week_of_month > 5:
                    raise ValueError("주차는 1-5 사이여야 합니다")
                
                # 해당 월의 첫째 날
                first_day = datetime(year, month, 1)
                # 첫째 날의 요일 (0=월요일, 6=일요일)
                first_weekday = first_day.weekday()
                
                # 해당 월의 첫 번째 주 시작일 (월요일 기준)
                first_monday = first_day - timedelta(days=first_weekday)
                
                # 지정된 주차의 시작일 (월요일)
                start_date = first_monday + timedelta(weeks=week_of_month-1)
                end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
                
                # 해당 월 범위를 벗어나지 않도록 조정
                month_start = datetime(year, month, 1)
                last_day = calendar.monthrange(year, month)[1]
                month_end = datetime(year, month, last_day, 23, 59, 59)
                
                # 시작일이 해당 월보다 이전이면 월 시작일로 조정
                if start_date < month_start:
                    start_date = month_start
                # 종료일이 해당 월보다 이후면 월 종료일로 조정
                if end_date > month_end:
                    end_date = month_end
                    
            except (ValueError, IndexError) as e:
                raise ValueError(f"잘못된 주차 형식입니다: {str(e)}. YYYY-MM-W 형식을 사용하세요 (예: 2024-10-2)")
            
        elif period_type == 'month':
            # 특정 월 (예: 2024-09)
            if not period_value:
                raise ValueError("month 타입은 period_value가 필요합니다 (형식: YYYY-MM)")
            year, month = period_value.split('-')
            year = int(year)
            month = int(month)
            start_date = datetime(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime(year, month, last_day, 23, 59, 59)
            
        elif period_type == 'year':
            # 특정 년도 (예: 2024)
            if not period_value:
                raise ValueError("year 타입은 period_value가 필요합니다 (형식: YYYY)")
            year = int(period_value)
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            
        elif period_type == 'all':
            # 전체 기간
            start_date = datetime(2020, 1, 1)  # 충분히 과거 날짜
            end_date = datetime.now()
            
        else:
            raise ValueError("Invalid period_type. Use 'day', 'week', 'month', 'year', or 'all'")
        
        return start_date, end_date

    def _calculate_profit_loss_rate(self, realized_profit_loss: float, sell_amount: float) -> tuple[float, float]:
        """
        수익률과 투자금액을 계산합니다.
        
        Args:
            realized_profit_loss: 실현 손익
            sell_amount: 매도 금액
        
        Returns:
            tuple[float, float]: (수익률(%), 투자금액)
        """
        # 투자금액 = 매도금액 - 실현손익
        invested_amount = sell_amount - realized_profit_loss if sell_amount > 0 else 0
        
        # 수익률 = (실현손익 / 투자금액) * 100
        profit_loss_rate = (realized_profit_loss / invested_amount * 100) if invested_amount > 0 else 0
        
        return round(profit_loss_rate, 2), invested_amount

    def _get_stock_type_filter(self, stock_type: str):
        """
        주식 유형에 따른 필터 조건을 반환합니다.
        
        Args:
            stock_type: 주식 유형 ('domestic', 'foreign', 'total')
        
        Returns:
            SQLAlchemy filter condition or None
        """
        if stock_type == 'domestic':
            # 국내주식: A로 시작하는 종목 코드
            return Transaction.stock_id.like('A%')
        elif stock_type == 'foreign':
            # 해외주식: US, NAS로 시작하는 종목 코드
            return Transaction.stock_id.regexp('^(US|NAS)')
        elif stock_type == 'total':
            # 전체: 필터 없음
            return None
        else:
            raise ValueError("Invalid stock_type. Use 'domestic', 'foreign', or 'total'")

    def get_period_realized_profit_loss(self, user_id: str, period_type: str, 
                                       period_value: Optional[str] = None, 
                                       stock_type: str = 'total') -> Dict[str, Any]:
        """
        특정 기간의 실현 손익을 조회합니다 (일별 상세 포함).
        
        Args:
            user_id: 사용자 ID
            period_type: 기간 타입 (day/week/month/year/all)
            period_value: 기간 값 (예: 2024-09-10, 2024-10-2, 2024-09, 2024)
            stock_type: 주식 유형 ('domestic', 'foreign', 'total')
        
        Returns:
            기간별 실현 손익 데이터 (일별 상세 포함)
        """
        from sqlalchemy import func
        from app.db.models.transaction import Transaction, TransactionType
        from collections import defaultdict
        
        # 기간 파싱
        start_date, end_date = self._parse_period_dates(period_type, period_value)
        
        # 주식 유형 필터
        stock_type_filter = self._get_stock_type_filter(stock_type)
        
        # 1. 일별 집계 데이터 조회 (DB에서 그룹화)
        daily_summary_query = self.db.query(
            func.date(Transaction.transaction_date).label('date'),
            func.sum(Transaction.krw_realized_profit_loss).label('total_pnl'),
            func.count(Transaction.id).label('trade_count')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL,
            Transaction.krw_realized_profit_loss.isnot(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
        
        # 주식 유형 필터 적용
        if stock_type_filter is not None:
            daily_summary_query = daily_summary_query.filter(stock_type_filter)
            
        daily_summary = daily_summary_query.group_by(
            func.date(Transaction.transaction_date)
        ).order_by(
            func.date(Transaction.transaction_date)
        ).all()
        
        # 2. 일별-종목별 상세 데이터 조회 (DB에서 그룹화)
        daily_stock_details_query = self.db.query(
            func.date(Transaction.transaction_date).label('date'),
            Transaction.stock_id,
            func.sum(Transaction.krw_realized_profit_loss).label('stock_pnl'),
            func.count(Transaction.id).label('stock_trades'),
            func.sum(Transaction.quantity).label('total_quantity'),
            func.avg(Transaction.price).label('avg_price'),
            func.group_concat(Transaction.id).label('transaction_ids'),  # MySQL용 GROUP_CONCAT
            # 환율 관련 컬럼 추가
            func.sum(Transaction.price_profit_loss).label('price_profit_loss'),
            func.sum(Transaction.exchange_profit_loss).label('exchange_profit_loss'),
            func.avg(Transaction.purchase_average_exchange_rate).label('avg_purchase_rate'),
            func.avg(Transaction.current_exchange_rate).label('avg_current_rate')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL,
            Transaction.krw_realized_profit_loss.isnot(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
        
        # 주식 유형 필터 적용
        if stock_type_filter is not None:
            daily_stock_details_query = daily_stock_details_query.filter(stock_type_filter)
            
        daily_stock_details = daily_stock_details_query.group_by(
            func.date(Transaction.transaction_date),
            Transaction.stock_id
        ).order_by(
            func.date(Transaction.transaction_date),
            Transaction.stock_id
        ).all()
        
        # 3. 전체 기간 집계 (투자금액 계산을 위해 추가 정보 조회)
        total_summary_query = self.db.query(
            func.sum(Transaction.krw_realized_profit_loss).label('total_pnl'),
            func.count(Transaction.id).label('total_trades'),
            func.sum(Transaction.quantity * Transaction.price).label('total_sell_amount'),
            func.sum(Transaction.quantity).label('total_quantity')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL,
            Transaction.krw_realized_profit_loss.isnot(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
        
        # 주식 유형 필터 적용
        if stock_type_filter is not None:
            total_summary_query = total_summary_query.filter(stock_type_filter)
            
        total_summary = total_summary_query.first()
        
        # 데이터 구조화
        daily_breakdown = []
        stock_details_by_date = defaultdict(list)
        
        # 일별-종목별 상세를 날짜별로 그룹화
        for detail in daily_stock_details:
            date_str = detail.date.strftime("%Y-%m-%d") if hasattr(detail.date, 'strftime') else str(detail.date)
            # transaction_ids 파싱 (GROUP_CONCAT 결과는 콤마로 구분된 문자열)
            transaction_ids = detail.transaction_ids.split(',') if detail.transaction_ids else []
            
            stock_detail = {
                'date': date_str,
                'stock_id': detail.stock_id,
                'stock_name': f"주식 {detail.stock_id}" if detail.stock_id else "알 수 없음",
                'realized_profit_loss': float(detail.stock_pnl or 0),
                'trade_count': int(detail.stock_trades or 0),
                'total_sell_quantity': int(detail.total_quantity or 0),
                'avg_sell_price': float(detail.avg_price or 0),
                'transaction_ids': transaction_ids
            }
            
            # 환율 관련 정보가 있는 경우에만 추가 (해외 주식)
            if detail.price_profit_loss is not None:
                stock_detail['price_profit_loss'] = float(detail.price_profit_loss or 0)
            if detail.exchange_profit_loss is not None:
                stock_detail['exchange_profit_loss'] = float(detail.exchange_profit_loss or 0)
            if detail.avg_purchase_rate is not None:
                stock_detail['avg_purchase_exchange_rate'] = float(detail.avg_purchase_rate or 0)
            if detail.avg_current_rate is not None:
                stock_detail['avg_current_exchange_rate'] = float(detail.avg_current_rate or 0)
            
            stock_details_by_date[date_str].append(stock_detail)
        
        # 일별 요약과 상세 결합
        for day in daily_summary:
            date_str = day.date.strftime("%Y-%m-%d") if hasattr(day.date, 'strftime') else str(day.date)
            daily_breakdown.append({
                'date': date_str,
                'total_realized_profit_loss': float(day.total_pnl or 0),
                'trade_count': int(day.trade_count or 0),
                'stock_details': stock_details_by_date.get(date_str, [])
            })
        
        # 수익률 계산
        total_pnl = float(total_summary.total_pnl or 0) if total_summary else 0
        total_sell_amount = float(total_summary.total_sell_amount or 0) if total_summary else 0
        
        profit_loss_rate, total_invested = self._calculate_profit_loss_rate(total_pnl, total_sell_amount)
        
        return {
            'period_type': period_type,
            'period_value': period_value,
            'total_realized_profit_loss': total_pnl,
            'total_trades': int(total_summary.total_trades or 0) if total_summary else 0,
            'total_profit_loss_rate': profit_loss_rate,
            'total_invested_amount': total_invested,
            'daily_breakdown': daily_breakdown
        }
    
    def get_stock_realized_profit_loss(self, user_id: str, period_type: str, 
                                      period_value: Optional[str] = None, 
                                      stock_type: str = 'total') -> Dict[str, Any]:
        """
        특정 기간의 종목별 실현 손익을 조회합니다.
        
        Args:
            user_id: 사용자 ID
            period_type: 기간 타입 (day/week/month/year/all)
            period_value: 기간 값 (예: 2024-09-10, 2024-10-2, 2024-09, 2024)
            stock_type: 주식 유형 ('domestic', 'foreign', 'total')
        
        Returns:
            종목별 실현 손익 데이터
        """
        from sqlalchemy import func
        from app.db.models.transaction import Transaction, TransactionType
        
        # 기간 파싱
        start_date, end_date = self._parse_period_dates(period_type, period_value)
        
        # 주식 유형 필터
        stock_type_filter = self._get_stock_type_filter(stock_type)
        
        # 1. 종목별 집계 데이터 조회 (DB에서 그룹화)
        stock_summary_query = self.db.query(
            Transaction.stock_id,
            func.sum(Transaction.krw_realized_profit_loss).label('total_pnl'),
            func.count(Transaction.id).label('trade_count'),
            func.sum(Transaction.quantity).label('total_quantity'),
            func.sum(Transaction.quantity * Transaction.price).label('total_sell_amount'),
            func.min(Transaction.transaction_date).label('first_date'),
            func.max(Transaction.transaction_date).label('last_date'),
            # 환율 관련 컬럼 추가
            func.sum(Transaction.price_profit_loss).label('total_price_pnl'),
            func.sum(Transaction.exchange_profit_loss).label('total_exchange_pnl'),
            func.avg(Transaction.purchase_average_exchange_rate).label('avg_purchase_rate'),
            func.avg(Transaction.current_exchange_rate).label('avg_current_rate')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL,
            Transaction.krw_realized_profit_loss.isnot(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
        
        # 주식 유형 필터 적용
        if stock_type_filter is not None:
            stock_summary_query = stock_summary_query.filter(stock_type_filter)
            
        stock_summary = stock_summary_query.group_by(
            Transaction.stock_id
        ).order_by(
            func.sum(Transaction.krw_realized_profit_loss).desc()  # 수익률 기준 정렬
        ).all()
        
        # 2. 전체 기간 집계
        total_summary_query = self.db.query(
            func.sum(Transaction.krw_realized_profit_loss).label('total_pnl'),
            func.count(Transaction.id).label('total_trades'),
            func.sum(Transaction.quantity * Transaction.price).label('total_sell_amount')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.SELL,
            Transaction.krw_realized_profit_loss.isnot(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
        
        # 주식 유형 필터 적용
        if stock_type_filter is not None:
            total_summary_query = total_summary_query.filter(stock_type_filter)
            
        total_summary = total_summary_query.first()
        
        # 종목별 데이터 구조화
        stocks = []
        for stock in stock_summary:
            stock_pnl = float(stock.total_pnl or 0)
            stock_trades = int(stock.trade_count or 0)
            stock_sell_amount = float(stock.total_sell_amount or 0)
            
            # 수익률 계산
            stock_profit_rate, stock_invested = self._calculate_profit_loss_rate(stock_pnl, stock_sell_amount)
            
            stock_data = {
                'stock_id': stock.stock_id,
                'stock_name': f"주식 {stock.stock_id}" if stock.stock_id else "알 수 없음",
                'total_realized_profit_loss': stock_pnl,
                'total_trades': stock_trades,
                'total_sell_quantity': int(stock.total_quantity or 0),
                'avg_profit_per_trade': stock_pnl / stock_trades if stock_trades > 0 else 0,
                'profit_loss_rate': stock_profit_rate,
                'total_invested_amount': stock_invested,
                'first_trade_date': stock.first_date.strftime("%Y-%m-%d") if stock.first_date else "",
                'last_trade_date': stock.last_date.strftime("%Y-%m-%d") if stock.last_date else ""
            }
            
            # 환율 관련 정보가 있는 경우에만 추가 (해외 주식)
            if stock.total_price_pnl is not None:
                stock_data['total_price_profit_loss'] = float(stock.total_price_pnl or 0)
            if stock.total_exchange_pnl is not None:
                stock_data['total_exchange_profit_loss'] = float(stock.total_exchange_pnl or 0)
            if stock.avg_purchase_rate is not None:
                stock_data['avg_purchase_exchange_rate'] = float(stock.avg_purchase_rate or 0)
            if stock.avg_current_rate is not None:
                stock_data['avg_current_exchange_rate'] = float(stock.avg_current_rate or 0)
            
            stocks.append(stock_data)
        
        # 전체 수익률 계산
        total_pnl = float(total_summary.total_pnl or 0) if total_summary else 0
        total_sell_amount = float(total_summary.total_sell_amount or 0) if total_summary else 0
        
        total_profit_rate, total_invested = self._calculate_profit_loss_rate(total_pnl, total_sell_amount)
        
        return {
            'period_type': period_type,
            'period_value': period_value,
            'total_realized_profit_loss': total_pnl,
            'total_trades': int(total_summary.total_trades or 0) if total_summary else 0,
            'total_profit_loss_rate': total_profit_rate,
            'total_invested_amount': total_invested,
            'stocks': stocks
        }
