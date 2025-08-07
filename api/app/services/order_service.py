import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.models.order import Order, OrderStatus, OrderType, OrderMethod
from app.db.models.portfolio import VirtualBalance
from app.utils.transaction_manager import TransactionManager
from app.exceptions.custom_exceptions import ValidationError, NotFoundError, InsufficientBalanceError


class OrderService:
    """주문 관련 비즈니스 로직을 처리하는 서비스"""

    def __init__(self, order_repository: OrderRepository, virtual_balance_repository: VirtualBalanceRepository):
        self.order_repository = order_repository
        self.virtual_balance_repository = virtual_balance_repository
        self.portfolio_repository = PortfolioRepository(order_repository.session)

    def create_order(self, user_id: str, order_data: Dict[str, Any]) -> Order:
        """새로운 주문을 생성합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            # 기본 주문 데이터 설정
            order_data['user_id'] = user_id
            order_data['order_status'] = OrderStatus.PENDING
            order_data['executed_quantity'] = Decimal('0')
            order_data['executed_amount'] = Decimal('0')
            order_data['commission'] = Decimal('0')
            order_data['tax'] = Decimal('0')
            order_data['total_fee'] = Decimal('0')
            
            # 주문 유효성 검증
            self._validate_order(order_data)
            
            # 잔고 확인 및 예약
            if order_data['order_type'] == OrderType.BUY:
                self._reserve_cash_for_buy_order(user_id, order_data)
            elif order_data['order_type'] == OrderType.SELL:
                self._validate_sell_order(user_id, order_data)
            
            # 주문 생성
            order = self.order_repository.create_order(order_data)
            
            # 시장가 주문인 경우 즉시 체결 시뮬레이션
            if order_data['order_method'] == OrderMethod.MARKET:
                self._execute_market_order(order)
            
            logging.info(f"Order created: {order.id} for user {user_id}")
            return order

    def create_quick_order(self, user_id: str, stock_id: str, order_type: OrderType, amount_or_quantity: Decimal) -> Order:
        """빠른 주문을 생성합니다."""
        # 현재가 조회 (실제로는 외부 API 호출)
        current_price = self._get_current_price(stock_id)
        
        if order_type == OrderType.BUY:
            # 매수: 금액 기준
            quantity = amount_or_quantity / current_price
            order_data = {
                'stock_id': stock_id,
                'order_type': order_type,
                'order_method': OrderMethod.MARKET,
                'quantity': quantity.quantize(Decimal('1')),  # 정수로 반올림
                'order_price': current_price
            }
        else:
            # 매도: 수량 기준
            order_data = {
                'stock_id': stock_id,
                'order_type': order_type,
                'order_method': OrderMethod.MARKET,
                'quantity': amount_or_quantity,
                'order_price': current_price
            }
        
        return self.create_order(user_id, order_data)

    def get_orders(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        status: Optional[OrderStatus] = None,
        order_type: Optional[OrderType] = None,
        stock_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """주문 목록을 조회합니다."""
        orders = self.order_repository.get_orders_by_user(user_id, page, size, status, order_type, stock_id)
        total = self.order_repository.count_orders_by_user(user_id, status, order_type, stock_id)
        
        return {
            'orders': orders,
            'total': total,
            'page': page,
            'size': size,
            'pages': (total + size - 1) // size
        }

    def get_order_by_id(self, user_id: str, order_id: str) -> Order:
        """특정 주문을 조회합니다."""
        order = self.order_repository.get_by_user_and_id(user_id, order_id)
        if not order:
            raise NotFoundError(f"Order {order_id} not found")
        return order

    def update_order(self, user_id: str, order_id: str, update_data: Dict[str, Any]) -> Order:
        """주문을 수정합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            order = self.get_order_by_id(user_id, order_id)
            
            if not self.order_repository.can_modify_order(order):
                raise ValidationError("Cannot modify order in current status")
            
            # 수정 가능한 필드만 업데이트
            allowed_fields = ['order_price', 'quantity', 'expires_at', 'notes']
            filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            # 수량 변경 시 잔고 재확인
            if 'quantity' in filtered_data and order.order_type == OrderType.BUY:
                self._validate_quantity_change(order, filtered_data['quantity'])
            
            updated_order = self.order_repository.update_order(order, filtered_data)
            logging.info(f"Order updated: {order_id} for user {user_id}")
            return updated_order

    def cancel_order(self, user_id: str, order_id: str, cancel_reason: Optional[str] = None) -> Order:
        """주문을 취소합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            order = self.get_order_by_id(user_id, order_id)
            
            if not self.order_repository.can_cancel_order(order):
                raise ValidationError("Cannot cancel order in current status")
            
            # 매수 주문 취소 시 예약된 현금 반환
            if order.order_type == OrderType.BUY:
                self._release_reserved_cash(order)
            
            cancelled_order = self.order_repository.cancel_order(order, cancel_reason)
            logging.info(f"Order cancelled: {order_id} for user {user_id}")
            return cancelled_order

    def get_order_summary(self, user_id: str, period_days: int = 30) -> Dict[str, Any]:
        """주문 요약 정보를 조회합니다."""
        return self.order_repository.get_order_summary(user_id, period_days)

    def get_pending_orders(self, user_id: str, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """대기중인 주문을 조회합니다."""
        orders = self.order_repository.get_pending_orders(user_id, page, size)
        total = self.order_repository.count_pending_orders(user_id)
        
        return {
            'orders': orders,
            'total': total,
            'page': page,
            'size': size,
            'pages': (total + size - 1) // size
        }

    def get_order_history(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """주문 이력을 조회합니다."""
        orders = self.order_repository.get_order_history(user_id, page, size, start_date, end_date)
        total = self.order_repository.count_order_history(user_id, start_date, end_date)
        
        return {
            'orders': orders,
            'total': total,
            'page': page,
            'size': size,
            'pages': (total + size - 1) // size
        }

    def execute_order(self, user_id: str, order_id: str, execution_price: Optional[Decimal] = None) -> Order:
        """주문을 강제로 체결합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            order = self.get_order_by_id(user_id, order_id)
            
            if order.order_status not in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                raise ValidationError("Cannot execute order in current status")
            
            # 체결가 결정
            if execution_price is None:
                execution_price = self._get_current_price(order.stock_id)
            
            # 체결 수량 (남은 수량 전체)
            remaining_quantity = order.quantity - order.executed_quantity
            
            # 수수료 계산
            commission = self._calculate_commission(execution_price * remaining_quantity)
            tax = self._calculate_tax(execution_price * remaining_quantity, order.order_type)
            
            # 주문 체결
            execution = self.order_repository.execute_order(
                order, execution_price, remaining_quantity, commission, tax
            )
            
            # 가상 잔고 업데이트
            self._update_virtual_balance_for_execution(order, execution)
            
            # 포트폴리오 업데이트
            self._update_portfolio_for_execution(order, execution)
            
            logging.info(f"Order executed: {order_id} for user {user_id}")
            return order

    def _validate_order(self, order_data: Dict[str, Any]) -> None:
        """주문 유효성을 검증합니다."""
        if order_data['quantity'] <= 0:
            raise ValidationError("Order quantity must be positive")
        
        if order_data['order_method'] == OrderMethod.LIMIT and not order_data.get('order_price'):
            raise ValidationError("Limit order requires order price")
        
        if order_data['order_method'] == OrderMethod.MARKET and order_data.get('order_price'):
            # 시장가 주문에서는 현재가 사용
            order_data['order_price'] = self._get_current_price(order_data['stock_id'])

    def _reserve_cash_for_buy_order(self, user_id: str, order_data: Dict[str, Any]) -> None:
        """매수 주문을 위한 현금을 예약합니다."""
        required_amount = order_data['quantity'] * order_data['order_price']
        
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        if not virtual_balance or virtual_balance.available_cash < required_amount:
            raise InsufficientBalanceError("Insufficient available cash for buy order")
        
        # 사용 가능한 현금에서 차감 (주문 완료/취소 시까지 예약)
        virtual_balance.available_cash -= required_amount

    def _validate_sell_order(self, user_id: str, order_data: Dict[str, Any]) -> None:
        """매도 주문을 검증합니다."""
        stock_id = order_data['stock_id']
        sell_quantity = order_data['quantity']
        
        # 포트폴리오에서 보유 수량 확인
        portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, stock_id)
        
        if not portfolio:
            raise ValidationError(f"주식 {stock_id}을(를) 보유하고 있지 않습니다")
        
        if portfolio.current_quantity < sell_quantity:
            raise ValidationError(
                f"보유 수량({portfolio.current_quantity})이 매도 수량({sell_quantity})보다 부족합니다"
            )

    def _execute_market_order(self, order: Order) -> None:
        """시장가 주문을 즉시 체결합니다."""
        current_price = self._get_current_price(order.stock_id)
        commission = self._calculate_commission(order.quantity * current_price)
        tax = self._calculate_tax(order.quantity * current_price, order.order_type)
        
        execution = self.order_repository.execute_order(
            order, current_price, order.quantity, commission, tax
        )
        
        self._update_virtual_balance_for_execution(order, execution)
        self._update_portfolio_for_execution(order, execution)

    def _get_current_price(self, stock_id: str) -> Decimal:
        """현재가를 조회합니다. (실제로는 외부 API 호출)"""
        # TODO: 실제 주가 API 연동
        # 현재는 임시로 10000원 반환
        return Decimal('10000')

    def _calculate_commission(self, amount: Decimal) -> Decimal:
        """거래 수수료를 계산합니다."""
        # 0.015% 수수료 (최소 500원)
        commission = amount * Decimal('0.00015')
        return max(commission, Decimal('500'))

    def _calculate_tax(self, amount: Decimal, order_type: OrderType) -> Decimal:
        """거래세를 계산합니다."""
        if order_type == OrderType.SELL:
            # 매도 시에만 0.23% 거래세
            return amount * Decimal('0.0023')
        return Decimal('0')

    def _update_virtual_balance_for_execution(self, order: Order, execution) -> None:
        """체결에 따라 가상 잔고를 업데이트합니다."""
        execution_amount = execution.execution_amount
        total_cost = execution_amount + order.commission + order.tax
        
        if order.order_type == OrderType.BUY:
            # 매수: 예약된 금액에서 실제 체결 금액 정산
            reserved_amount = order.quantity * order.order_price
            actual_amount = total_cost
            difference = reserved_amount - actual_amount
            
            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            virtual_balance.available_cash += difference  # 차액 반환
            virtual_balance.cash_balance -= actual_amount  # 실제 금액 차감
            virtual_balance.invested_amount += execution_amount
            
        elif order.order_type == OrderType.SELL:
            # 매도: 현금 증가
            net_amount = execution_amount - order.commission - order.tax
            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            virtual_balance.cash_balance += net_amount
            virtual_balance.available_cash += net_amount
            virtual_balance.invested_amount -= execution_amount

    def _release_reserved_cash(self, order: Order) -> None:
        """취소된 매수 주문의 예약 현금을 반환합니다."""
        if order.order_type == OrderType.BUY:
            remaining_quantity = order.quantity - order.executed_quantity
            reserved_amount = remaining_quantity * order.order_price
            
            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            virtual_balance.available_cash += reserved_amount

    def _validate_quantity_change(self, order: Order, new_quantity: Decimal) -> None:
        """수량 변경 시 잔고를 재확인합니다."""
        if order.order_type == OrderType.BUY:
            old_amount = order.quantity * order.order_price
            new_amount = new_quantity * order.order_price
            amount_difference = new_amount - old_amount
            
            if amount_difference > 0:
                virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
                if virtual_balance.available_cash < amount_difference:
                    raise InsufficientBalanceError("Insufficient available cash for quantity increase")

    def _update_portfolio_for_execution(self, order: Order, execution) -> None:
        """체결에 따라 포트폴리오를 업데이트합니다."""
        user_id = order.user_id
        stock_id = order.stock_id
        quantity = execution.execution_quantity
        price = execution.execution_price
        
        # 기존 포트폴리오 조회
        portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, stock_id)
        
        if order.order_type == OrderType.BUY:
            if portfolio:
                # 기존 포트폴리오가 있는 경우 매수 업데이트
                self.portfolio_repository.update_portfolio_buy(portfolio, quantity, price)
            else:
                # 새로운 포트폴리오 생성
                self.portfolio_repository.create_portfolio(user_id, stock_id, quantity, price)
                
        elif order.order_type == OrderType.SELL:
            if portfolio:
                # 매도 업데이트
                self.portfolio_repository.update_portfolio_sell(portfolio, quantity, price)
                
                # 보유 수량이 0이 되면 포트폴리오 삭제
                if portfolio.current_quantity == 0:
                    self.portfolio_repository.delete_empty_portfolio(portfolio)
            else:
                # 포트폴리오가 없는데 매도하려는 경우 (이론상 발생하지 않아야 함)
                raise ValidationError("Cannot sell stock not in portfolio")
        
        logging.info(f"Portfolio updated for execution: {order.id}, {order.order_type.value} {quantity} shares at {price}")
