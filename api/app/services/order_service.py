import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.services.transaction_service import TransactionService

from app.db.models.order import Order, OrderStatus, OrderType, OrderMethod, ExitReason
from app.db.models.virtual_balance import VirtualBalance
from app.services.toss_proxy_service import TossProxyService
from app.utils.transaction_manager import TransactionManager
from app.exceptions.custom_exceptions import ValidationError, NotFoundError, InsufficientBalanceError
from app.api.v1.schemas.stock_schemas import StockPriceDetailsResponse


class OrderService:
    """주문 관련 비즈니스 로직을 처리하는 서비스"""

    def __init__(self, order_repository: OrderRepository, virtual_balance_repository: VirtualBalanceRepository, toss_proxy_service: TossProxyService):
        self.order_repository = order_repository
        self.virtual_balance_repository = virtual_balance_repository
        self.portfolio_repository = PortfolioRepository(order_repository.session)
        self.transaction_service = TransactionService(order_repository.session)

        self.toss_proxy_service = toss_proxy_service

    def create_order(self, user_id: str, order_data: Dict[str, Any]) -> Order:
        """새로운 주문을 생성합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            # 사용자 존재 여부 선검증 (FK 에러를 사전에 방지하고 명확한 오류 제공)
            user_repo = UserRepository(self.order_repository.session)
            if not user_repo.get_by_id(user_id):
                raise NotFoundError("User not found")

            # 1) 현재 주식 가격/통화 조회
            stock_id = order_data.get('stock_id')
            if not stock_id:
                raise ValidationError("stock_id is required")
            current_price, currency = self._fetch_price_and_currency(stock_id)
            
            # 2) 주문가 결정
            order_data['order_price'] = self._determine_order_price(order_data, current_price)
            
            # 모델 호환성: stock_id -> product_code 매핑 및 기본 상품 정보 설정
            order_data['product_code'] = stock_id
            # product_name, market은 응답에서 유추하거나 기본값 사용
            # price_data는 _fetch_price_and_currency 내부에서만 사용되므로 market/이름은 입력값 기반으로 처리
            order_data['product_name'] = order_data.get('product_name') or stock_id
            order_data['market'] = order_data.get('market') or 'UNKNOWN'
            # 더 이상 모델에 없는 필드는 제거
            if 'stock_id' in order_data:
                order_data.pop('stock_id')
            
            # 3) 환율/원화 환산 적용
            self._apply_exchange_and_price(order_data, currency)
            
            # 4) 기본 필드 설정
            self._set_default_order_fields(order_data, user_id)
            
            # 주문 유효성 검증 (컨트롤러에서 이미 DB Enum으로 변환됨)
            self._validate_order(order_data)

            # 주문 타입별 잔고/보유 주식 검증 및 예약
            if order_data['order_type'] == OrderType.BUY:
                # 매수 주문 잔고 검증
                if order_data['order_method'] == OrderMethod.LIMIT:
                    # 지정가 매수: 정확한 가격으로 사전 예약
                    self._reserve_cash_for_buy_order(user_id, order_data)
                elif order_data['order_method'] == OrderMethod.MARKET:
                    # 시장가 매수: 체결 시 실시간 검증 (사전 예약 없음)
                    # 이유: 실제 체결 가격을 알 수 없어 정확한 예약이 불가능
                    logging.info(f"시장가 매수 주문은 체결 시 실시간 잔고 검증 - User: {user_id}")
            elif order_data['order_type'] == OrderType.SELL:
                # 매도 주문: 보유 주식 수량 검증 (예약된 수량 고려)
                self._validate_sell_order(user_id, order_data)
            
            # 주문 생성
            order = self.order_repository.create_order(order_data)
            
            # 시장가 주문인 경우 즉시 체결 시뮬레이션
            # (이미 create_order에서 현재가를 조회했으므로 중복 조회 없음)
            if order_data['order_method'] == OrderMethod.MARKET:
                self._execute_market_order(order)
            
            logging.info(f"Order created: {order.id} for user {user_id}")
            return order

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
        
        return self._create_paginated_response(orders, total, page, size)

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
            if 'quantity' in filtered_data:
                if order.order_type == OrderType.BUY:
                    self._validate_quantity_change(order, filtered_data['quantity'])
                elif order.order_type == OrderType.SELL:
                    # SELL 주문 수정 시 과다 매도 방지: 예약 수량 반영(본 주문 제외)
                    reserved_quantity = self.order_repository.get_pending_sell_reserved_quantity(
                        user_id, self._get_product_code(order), exclude_order_id=order.id
                    )
                    portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, self._get_product_code(order))
                    available_to_sell = portfolio.current_quantity - reserved_quantity
                    new_quantity = filtered_data['quantity']
                    # 이미 일부 체결되었으면 남은 수량 기준으로 비교
                    remaining_to_sell = new_quantity - order.executed_quantity
                    if remaining_to_sell < 0:
                        remaining_to_sell = Decimal('0')
                    if available_to_sell < remaining_to_sell:
                        raise ValidationError(
                            f"매도 가능 수량({available_to_sell})이 수정 후 남은 매도 수량({remaining_to_sell})보다 부족합니다"
                        )
            
            updated_order = self.order_repository.update_order(order, filtered_data)
            logging.info(f"Order updated: {order_id} for user {user_id}")
            return updated_order

    def cancel_order(self, user_id: str, order_id: str, cancel_reason: Optional[str] = None) -> Order:
        """주문을 취소합니다."""
        with TransactionManager.transaction(self.order_repository.session):
            order = self.get_order_by_id(user_id, order_id)
            
            if not self.order_repository.can_cancel_order(order):
                raise ValidationError("대기중이거나 부분체결된 주문만 취소 가능합니다.")
            
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
        
        return self._create_paginated_response(orders, total, page, size)

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

        return self._create_paginated_response(orders, total, page, size)

    def _validate_order(self, order_data: Dict[str, Any]) -> None:
        """
        주문 기본 유효성을 검증합니다.
        
        주의: 
        - 시장가 주문의 경우 실제 체결 가격은 _execute_market_order()에서 결정됩니다
        - 잔고 및 보유 주식 검증은 별도로 수행됩니다:
          - 매수 주문: _reserve_cash_for_buy_order()에서 잔고 확인 및 예약
          - 매도 주문: _validate_sell_order()에서 보유 주식 수량 확인
        """
        if order_data['quantity'] <= 0:
            raise ValidationError("Order quantity must be positive")
        
        if order_data['order_method'] == OrderMethod.LIMIT and not order_data.get('order_price'):
            raise ValidationError("Limit order requires order price")
        
        # 지정가 주문의 경우에만 주문 가격 검증
        if order_data['order_method'] == OrderMethod.LIMIT and order_data.get('order_price', 0) <= 0:
            raise ValidationError("Limit order price must be positive")
        
        # 시장가 주문의 경우 order_price는 참고용이며, 실제 체결은 _execute_market_order에서 현재가로 진행

    def _reserve_cash_for_buy_order(self, user_id: str, order_data: Dict[str, Any]) -> None:
        """
        지정가 매수 주문을 위한 현금을 예약합니다.
        
        주의: 시장가 주문은 이 함수를 호출하지 않습니다. 
        시장가 주문의 잔고 검증은 _execute_market_order()에서 실시간으로 수행됩니다.
        
        Args:
            user_id: 사용자 ID
            order_data: 주문 데이터 (quantity, order_price, currency 등 포함)
            
        Raises:
            InsufficientBalanceError: 잔고 부족 시
        """
        quantity = order_data['quantity']
        order_price = order_data['order_price']
        currency = order_data.get('currency', 'KRW')
        product_code = self._get_product_code(order_data)
        exchange_rate = order_data.get('exchange_rate')
        
        # 원화 환산 금액 계산 (create_order에서 이미 krw_order_price 설정됨)
        krw_order_price = order_data.get('krw_order_price', order_price)
        krw_order_amount = quantity * krw_order_price
            
        # 예상 수수료 및 세금 계산 (원화 기준)
        expected_commission = self._calculate_commission(krw_order_amount)
        expected_tax = Decimal('0')  # 매수 시 세금 없음
        required_amount = krw_order_amount + expected_commission + expected_tax

        # 사용자 잔고 조회
        virtual_balance = self.virtual_balance_repository.get_by_user_id(user_id)
        
        if not virtual_balance:
            raise InsufficientBalanceError("가상 잔고를 찾을 수 없습니다")
            
        # 잔고 부족 검증 (상세한 정보 포함)
        if virtual_balance.available_cash < required_amount:
            raise self._create_insufficient_balance_error(
                required_amount=required_amount,
                available_cash=virtual_balance.available_cash,
                order_amount=krw_order_amount,
                commission=expected_commission,
                tax=expected_tax,
                currency=currency,
                original_price=order_price,
                quantity=quantity,
                exchange_rate=exchange_rate
            )

        # 로깅: 주문 정보 (환율 포함)
        self._log_order_info(
            action="매수 주문 잔고 예약",
            user_id=user_id,
            product_code=product_code,
            quantity=quantity,
            price=order_price,
            currency=currency,
            exchange_rate=exchange_rate,
            required_amount=required_amount,
            available_cash=virtual_balance.available_cash
        )

        # 사용 가능한 현금에서 차감 (주문 완료/취소 시까지 예약)
        virtual_balance.available_cash -= required_amount

        # 변경사항을 DB에 즉시 반영
        self.virtual_balance_repository.session.flush()
        
        logging.info(f"잔고 예약 완료 - 예약 후 가용 잔고: {virtual_balance.available_cash:,.0f}원")

    def _validate_sell_order(self, user_id: str, order_data: Dict[str, Any]) -> None:
        """
        매도 주문을 검증합니다.
        
        Args:
            user_id: 사용자 ID
            order_data: 주문 데이터 (product_code/stock_id, quantity 포함)
            
        Raises:
            ValidationError: 보유 주식 부족 시
        """
        stock_id = order_data.get('product_code') or order_data['stock_id']
        sell_quantity = order_data['quantity']
        order_price = order_data.get('order_price', 0)
        
        # 포트폴리오에서 보유 수량 확인
        portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, stock_id)

        if not portfolio or not portfolio.is_active:
            raise ValidationError(f"종목 {stock_id}을(를) 보유하고 있지 않습니다")
        
        # 대기/부분체결 SELL 주문의 잔여 수량 예약치를 반영하여 검증
        reserved_quantity = self.order_repository.get_pending_sell_reserved_quantity(user_id, stock_id)
        available_to_sell = portfolio.current_quantity - reserved_quantity
        
        # 로깅: 매도 주문 정보
        self._log_order_info(
            action="매도 주문 검증",
            user_id=user_id,
            product_code=stock_id,
            quantity=sell_quantity,
            price=order_price
        )
        logging.info(f"보유 수량: {portfolio.current_quantity}, 예약 수량: {reserved_quantity}, "
                    f"매도 가능 수량: {available_to_sell}")
        
        if available_to_sell < sell_quantity:
            raise ValidationError(
                f"매도 가능 수량이 부족합니다. "
                f"매도 요청: {sell_quantity}주, "
                f"매도 가능: {available_to_sell}주 "
                f"(보유: {portfolio.current_quantity}주 - 예약: {reserved_quantity}주)"
            )
            
        logging.info(f"매도 주문 검증 완료 - 종목: {stock_id}, 매도 수량: {sell_quantity}주")

    def _execute_market_order(self, order: Order) -> None:
        """시장가 주문을 즉시 체결합니다.
        
        주의: 시장가 주문의 경우 create_order에서 이미 현재가를 조회하여 
        order.order_price에 설정했으므로 다시 조회하지 않습니다.
        """
        # 시장가 주문은 이미 create_order에서 현재가를 설정함
        current_price = order.order_price
        
        # 환율도 이미 order에 설정되어 있음 (create_order에서 처리)
        exchange_rate = order.exchange_rate or Decimal('1.0')
        
        # 원화 환산 금액 계산
        if order.currency == 'KRW':
            krw_order_amount = order.quantity * current_price
        else:
            # 해외자산: 이미 설정된 환율 사용
            krw_order_amount = order.quantity * current_price * exchange_rate
        
        commission = self._calculate_commission(krw_order_amount)
        tax = self._calculate_tax(krw_order_amount, order.order_type)
        
        # 시장가 주문의 경우 실제 체결 가격으로 실시간 잔고 재검증
        if order.order_type == OrderType.BUY:
            # 환율 정보 업데이트 (해외자산의 경우)
            if order.currency != 'KRW':
                order.exchange_rate = exchange_rate
                order.krw_executed_amount = krw_order_amount
            
            total_required = krw_order_amount + commission + tax
            
            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            if not virtual_balance:
                raise ValidationError("Virtual balance not found")
                
            if virtual_balance.available_cash < total_required:
                logging.error(f"Market buy order balance validation failed - User: {order.user_id}, "
                            f"Required: {total_required}, Available: {virtual_balance.available_cash}")
                
                raise self._create_insufficient_balance_error(
                    required_amount=total_required,
                    available_cash=virtual_balance.available_cash,
                    order_amount=krw_order_amount,
                    commission=commission,
                    tax=tax,
                    currency=order.currency,
                    original_price=current_price,
                    quantity=order.quantity,
                    exchange_rate=exchange_rate
                )
                
        elif order.order_type == OrderType.SELL:
            # 매도: 보유 주식 수량 재검증 (pending 주문 고려)
            product_code = self._get_product_code(order)
            portfolio = self.portfolio_repository.get_by_user_and_stock(order.user_id, product_code)
            if not portfolio or not portfolio.is_active:
                raise ValidationError(f"해당 자산을 보유하고 있지 않습니다: {product_code} ({order.product_name})")
            
            pending_sell_reserved = self.order_repository.get_pending_sell_reserved_quantity(
                order.user_id, product_code
            )
            available_to_sell = portfolio.current_quantity - pending_sell_reserved
            
            if order.quantity > available_to_sell:
                asset_type = "주" if order.currency == 'KRW' else "units"
                logging.error(f"Market sell order validation failed - User: {order.user_id}, "
                            f"Product: {product_code}, Requested: {order.quantity}, Available: {available_to_sell}, "
                            f"Owned: {portfolio.current_quantity}, Reserved: {pending_sell_reserved}")
                raise ValidationError(
                    f"매도 가능한 수량이 부족합니다. 요청: {order.quantity}{asset_type}, "
                    f"매도 가능: {available_to_sell}{asset_type} "
                    f"(보유: {portfolio.current_quantity}{asset_type} - 예약: {pending_sell_reserved}{asset_type})"
                )
        
        # 시장가 주문 검증 통과 로그
        logging.info(f"Market order validation passed - Order: {order.id}, "
                    f"Price: {current_price} {order.currency}"
                    f"{f' (환율: {exchange_rate})' if order.currency != 'KRW' else ''}, "
                    f"Total: {krw_order_amount + commission + tax:,.0f} KRW")
        
        # 체결 실행 (환율 정보 포함)
        execution = self.order_repository.execute_order(
            order, current_price, order.quantity, commission, tax
        )
        
        # 환율 정보가 있는 경우 execution에도 설정
        if order.currency != 'KRW' and hasattr(execution, 'exchange_rate'):
            execution.exchange_rate = order.exchange_rate
            execution.krw_execution_price = current_price * order.exchange_rate
            execution.krw_execution_amount = order.quantity * execution.krw_execution_price
        
        # 거래 내역을 먼저 생성하여 cash_before/after를 정확히 기록
        self._create_transaction_for_execution(order, execution)
        self._update_virtual_balance_for_execution(order, execution)
        self._update_portfolio_for_execution(order, execution)


    def _calculate_commission(self, amount: Decimal) -> Decimal:
        """거래 수수료를 계산합니다."""
        return Decimal('0') 
        # 0.015% 수수료 (최소 500원)
        commission = amount * Decimal('0.00015')
        return max(commission, Decimal('500'))

    def _calculate_tax(self, amount: Decimal, order_type: OrderType) -> Decimal:
        """거래세를 계산합니다."""
        return Decimal('0') 
        if order_type == OrderType.SELL:
            # 매도 시에만 0.23% 거래세
            return amount * Decimal('0.0023')
        return Decimal('0')

    def _update_virtual_balance_for_execution(self, order: Order, execution) -> None:
        """체결에 따라 가상 잔고를 업데이트합니다."""
        execution_amount = execution.execution_amount

        if order.order_type == OrderType.BUY:
            # 실행된 부분에 대한 예상 수수료(예약 시점과 동일한 방식)과 실제 수수료 비교
            expected_commission = self._calculate_commission(execution_amount)
            expected_tax = Decimal('0')  # 매수 시 세금 없음

            actual_commission = execution.execution_fee
            actual_tax = self._calculate_tax(execution_amount, order.order_type)

            reserved_for_executed = execution_amount + expected_commission + expected_tax
            actual_for_executed = execution_amount + actual_commission + actual_tax
            difference = reserved_for_executed - actual_for_executed

            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            # 예약 환불(차액만큼 반환) + 실제 현금 차감
            previous_cash = virtual_balance.cash_balance
            virtual_balance.available_cash += difference
            virtual_balance.cash_balance -= actual_for_executed
            # 총계 누적 및 원가(=체결금액) 투자 증가
            virtual_balance.total_buy_amount += execution_amount
            virtual_balance.total_commission += (actual_commission or Decimal('0'))
            virtual_balance.total_tax += (actual_tax or Decimal('0'))
            virtual_balance.invested_amount += execution_amount
            # 이력 기록 (BUY)
            try:
                self.virtual_balance_repository._add_balance_history(
                    virtual_balance_id=virtual_balance.id,
                    previous_cash=previous_cash,
                    new_cash=virtual_balance.cash_balance,
                    change_amount=-actual_for_executed,
                    change_type='BUY',
                    related_order_id=order.id,
                    description=f"BUY executed: {execution.execution_quantity} @ {execution.execution_price}"
                )
            except Exception:
                pass

        elif order.order_type == OrderType.SELL:
            # 매도: 실행 금액에서 수수료/세금 차감한 순입금 처리
            actual_commission = execution.execution_fee
            actual_tax = self._calculate_tax(execution_amount, order.order_type)
            net_amount = execution_amount - actual_commission - actual_tax

            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            previous_cash = virtual_balance.cash_balance
            virtual_balance.cash_balance += net_amount
            virtual_balance.available_cash += net_amount
            # 총계 누적
            virtual_balance.total_sell_amount += execution_amount
            virtual_balance.total_commission += (actual_commission or Decimal('0'))
            virtual_balance.total_tax += (actual_tax or Decimal('0'))
            # 이력 기록 (SELL)
            try:
                self.virtual_balance_repository._add_balance_history(
                    virtual_balance_id=virtual_balance.id,
                    previous_cash=previous_cash,
                    new_cash=virtual_balance.cash_balance,
                    change_amount=net_amount,
                    change_type='SELL',
                    related_order_id=order.id,
                    description=f"SELL executed: {execution.execution_quantity} @ {execution.execution_price}"
                )
            except Exception:
                pass

    def _release_reserved_cash(self, order: Order) -> None:
        """취소된 매수 주문의 예약 현금을 반환합니다."""
        if order.order_type == OrderType.BUY:
            remaining_quantity = order.quantity - order.executed_quantity
            amount = remaining_quantity * order.order_price
            # 예약 시점과 동일한 방식으로 수수료 계산
            expected_commission = self._calculate_commission(amount)
            expected_tax = Decimal('0')
            reserved_amount = amount + expected_commission + expected_tax
            
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
        stock_id = self._get_product_code(order)
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
                # SELL 체결의 손익에 따라 주문의 exit_reason 자동 설정 (평균단가 대비)
                try:
                    if price > portfolio.average_price:
                        order.exit_reason = ExitReason.TAKE_PROFIT
                    elif price < portfolio.average_price:
                        order.exit_reason = ExitReason.STOP_LOSS
                    else:
                        order.exit_reason = None
                except Exception:
                    # 비교 실패 시 설정 생략
                    order.exit_reason = None

                # 매도 업데이트 (원가 기준 invested_amount 감소)
                cost_basis_reduction = portfolio.average_price * quantity
                vb = self.virtual_balance_repository.get_by_user_id(user_id)
                if vb.invested_amount <= cost_basis_reduction:
                    vb.invested_amount = Decimal('0')
                else:
                    vb.invested_amount -= cost_basis_reduction

                # 포트폴리오 수량/평단 업데이트
                self.portfolio_repository.update_portfolio_sell(portfolio, quantity, price)
                
                # 보유 수량이 0이 되면 포트폴리오 삭제
                if portfolio.current_quantity == 0:
                    self.portfolio_repository.delete_empty_portfolio(portfolio)
            else:
                # 포트폴리오가 없는데 매도하려는 경우 (이론상 발생하지 않아야 함)
                raise ValidationError("Cannot sell stock not in portfolio")
        
        logging.info(f"Portfolio updated for execution: {order.id}, {order.order_type.value} {quantity} shares at {price}")

    def _create_transaction_for_execution(self, order: Order, execution) -> None:
        """체결에 따라 거래 내역을 생성합니다."""
        from app.db.models.transaction import TransactionType
        
        # 거래 유형 변환
        transaction_type = TransactionType.BUY if order.order_type == OrderType.BUY else TransactionType.SELL
        
        # 거래 내역 생성
        transaction = self.transaction_service.create_transaction_from_order(
            user_id=order.user_id,
            order_id=order.id,
            stock_id=self._get_product_code(order),
            transaction_type=transaction_type,
            quantity=execution.execution_quantity,
            price=execution.execution_price,
            commission=order.commission,
            tax=order.tax,
            description=f"{order.order_type.value} 주문 체결: {execution.execution_quantity}주 @ {execution.execution_price}"
        )
        
        logging.info(f"Transaction created for execution: {transaction.id}")

    # ==================== 헬퍼 메서드들 ====================

    def _get_product_code(self, order_or_data) -> str:
        """Order 객체나 order_data에서 product_code를 추출합니다."""
        if isinstance(order_or_data, Order):
            return order_or_data.product_code or order_or_data.stock_id
        else:
            return order_or_data.get('product_code', order_or_data.get('stock_id', 'Unknown'))

    def _fetch_price_and_currency(self, stock_id: str) -> tuple[Decimal, str]:
        """주식 현재가와 통화를 조회하여 반환합니다."""
        try:
            stock_price_raw = self.toss_proxy_service.get_stock_price_details(stock_id)
            stock_price_response = StockPriceDetailsResponse(**stock_price_raw)
            if not stock_price_response.result:
                raise ValidationError(f"No price data found for stock: {stock_id}")
            price_data = stock_price_response.result[0]
            current_price = Decimal(str(price_data.close))
            currency = price_data.currency
            return current_price, currency
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to get stock price for {stock_id}: {str(e)}")

    def _determine_order_price(self, order_data: Dict[str, Any], current_price: Decimal) -> Decimal:
        """주문가를 결정합니다. 시장가는 현재가, 지정가는 입력가를 사용합니다."""
        if order_data.get('order_method') == OrderMethod.MARKET:
            logging.info(f"Market order using current price: {current_price}")
            return current_price
        if not order_data.get('order_price'):
            raise ValidationError("Limit order requires order_price")
        return order_data['order_price']

    def _apply_exchange_and_price(self, order_data: Dict[str, Any], currency: str) -> None:
        """통화에 따라 환율 적용 및 원화 환산 가격을 설정합니다."""
        order_data['currency'] = currency
        if currency != 'KRW':
            exchange_rate = self.toss_proxy_service.get_exchange_rate(currency)
            order_data['exchange_rate'] = exchange_rate
            order_data['krw_order_price'] = order_data['order_price'] * exchange_rate
            logging.info(
                f"Foreign asset order: {order_data['order_price']} {currency} = "
                f"{order_data['krw_order_price']:.0f} KRW (rate: {exchange_rate})"
            )
        else:
            order_data['exchange_rate'] = None
            order_data['krw_order_price'] = order_data['order_price']

    def _set_default_order_fields(self, order_data: Dict[str, Any], user_id: str) -> None:
        """주문의 기본 필드를 설정합니다."""
        order_data['user_id'] = user_id
        order_data['order_status'] = OrderStatus.PENDING
        order_data['executed_quantity'] = Decimal('0')
        order_data['executed_amount'] = Decimal('0')
        order_data['commission'] = Decimal('0')
        order_data['tax'] = Decimal('0')
        order_data['total_fee'] = Decimal('0')

    def _create_paginated_response(self, items: list, total: int, page: int, size: int) -> Dict[str, Any]:
        """페이지네이션 응답을 생성합니다."""
        return {
            'orders': items,
            'total': total,
            'page': page,
            'size': size,
            'pages': (total + size - 1) // size
        }

    def _create_insufficient_balance_error(self, 
                                         required_amount: Decimal,
                                         available_cash: Decimal,
                                         order_amount: Decimal,
                                         commission: Decimal,
                                         tax: Decimal = Decimal('0'),
                                         currency: str = 'KRW',
                                         original_price: Optional[Decimal] = None,
                                         quantity: Optional[Decimal] = None,
                                         exchange_rate: Optional[Decimal] = None) -> InsufficientBalanceError:
        """잔고 부족 에러 메시지를 생성합니다."""
        if currency == 'KRW':
            return InsufficientBalanceError(
                f"가용 잔고가 부족합니다. "
                f"필요 금액: {required_amount:,.0f}원 "
                f"(주문금액: {order_amount:,.0f}원 + 수수료: {commission:,.0f}원"
                f"{f' + 세금: {tax:,.0f}원' if tax > 0 else ''}), "
                f"가용 잔고: {available_cash:,.0f}원"
            )
        else:
            return InsufficientBalanceError(
                f"가용 잔고가 부족합니다. "
                f"필요 금액: {required_amount:,.0f}원 "
                f"(주문금액: {original_price} {currency} × {quantity} = {order_amount:,.0f}원 "
                f"+ 수수료: {commission:,.0f}원"
                f"{f' + 세금: {tax:,.0f}원' if tax > 0 else ''}), "
                f"환율: {exchange_rate}, 가용 잔고: {available_cash:,.0f}원"
            )

    def _log_order_info(self, 
                       action: str,
                       user_id: str, 
                       product_code: str,
                       quantity: Decimal,
                       price: Decimal,
                       currency: str = 'KRW',
                       exchange_rate: Optional[Decimal] = None,
                       required_amount: Optional[Decimal] = None,
                       available_cash: Optional[Decimal] = None) -> None:
        """주문 정보를 로깅합니다."""
        if currency == 'KRW':
            logging.info(
                f"{action} - 사용자: {user_id}, 종목: {product_code}, "
                f"수량: {quantity}, 가격: {price:,.0f}원"
                f"{f', 필요 금액: {required_amount:,.0f}원' if required_amount else ''}"
                f"{f', 가용 잔고: {available_cash:,.0f}원' if available_cash else ''}"
            )
        else:
            krw_amount = quantity * price * (exchange_rate or 1)
            logging.info(
                f"{action} - 사용자: {user_id}, 종목: {product_code}, "
                f"수량: {quantity}, 가격: {price} {currency} "
                f"(환율: {exchange_rate}, 원화환산: {krw_amount:,.0f}원)"
                f"{f', 필요 금액: {required_amount:,.0f}원' if required_amount else ''}"
                f"{f', 가용 잔고: {available_cash:,.0f}원' if available_cash else ''}"
            )
