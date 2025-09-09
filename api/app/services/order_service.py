import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.transaction_repository import TransactionRepository
from app.services.transaction_service import TransactionService

from app.db.models.order import Order, OrderStatus, OrderType, OrderMethod, ExitReason
from app.db.models.transaction import Transaction
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
        
        db_session = order_repository.session
        self.transaction_service = TransactionService(
            db=db_session,
            transaction_repository=TransactionRepository(db_session),
            virtual_balance_repository=self.virtual_balance_repository,
            portfolio_repository=self.portfolio_repository
        )

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
            # 업종 정보 초기화 및 종목 개요 조회로 product_name, market(한국어 우선) 설정
            industry_code = None
            industry_display = None
            try:
                overview_raw = self.toss_proxy_service.get_stock_overview(stock_id)
                ov = overview_raw.get('result') if isinstance(overview_raw, dict) else None
                company = (ov or {}).get('company', {}) if isinstance(ov, dict) else {}
                market_info = (ov or {}).get('market', {}) if isinstance(ov, dict) else {}
                product_name = company.get('fullName') or company.get('name') 
                market_display = market_info.get('displayName') or market_info.get('code') or ''
                industry = company.get('industry', {}) if isinstance(ov, dict) else {}
                industry_code = industry.get('code')
                industry_display = industry.get('displayName') 

                logging.info(f"##> industry_code: {industry_code}, industry_display: {industry_display}")

                order_data['product_name'] = product_name
                order_data['market'] = market_display
            except Exception:
                # 실패 시 기본값 유지
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
                # 매도 주문: 지정가만 사전 검증, 시장가는 체결 직전 검증으로 위임
                if order_data['order_method'] == OrderMethod.LIMIT:
                    self._validate_sell_order(user_id, order_data)
                else:
                    logging.info(f"시장가 매도 주문은 체결 시 실시간 보유 수량 검증 - User: {user_id}")
            
            # 주문 생성
            order = self.order_repository.create_order(order_data)
            # 업종 정보는 Order 모델 컬럼이 아니므로 임시 속성으로 보관(포트폴리오 생성 시 사용)
            try:
                if industry_code:
                    setattr(order, 'industry_code', industry_code)
                if industry_display:
                    setattr(order, 'industry_display', industry_display)
            except Exception:
                pass
            
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
        """매도 주문 검증(사전 검증용). 시장가는 실행 시점 검증으로 위임."""
        stock_id = order_data.get('product_code') or order_data['stock_id']
        self._assert_sell_quantity_available(
            user_id=user_id,
            product_code=stock_id,
            requested_quantity=order_data['quantity'],
            price=order_data.get('order_price', 0),
            exclude_order_id=None,
            currency=order_data.get('currency', 'KRW'),
        )

    def _execute_market_order(self, order: Order) -> None:
        """시장가 주문을 즉시 체결합니다.
        
        주의: 시장가 주문의 경우 create_order에서 이미 현재가를 조회하여 
        order.order_price에 설정했으므로 다시 조회하지 않습니다.
        """
        # 시장가 주문은 이미 create_order에서 현재가를 설정함
        current_price = order.order_price
        
        # 환율도 이미 order에 설정되어 있음 (create_order에서 처리)
        exchange_rate = order.exchange_rate or Decimal('1.0')
        
        # 원화 환산 금액 계산 (통화와 무관하게 최종 KRW 금액 산출)
        if order.currency == 'KRW':
            krw_order_amount = order.quantity * current_price
        else:
            krw_order_amount = order.quantity * current_price * exchange_rate
        
        commission = self._calculate_commission(krw_order_amount)
        tax = self._calculate_tax(krw_order_amount, order.order_type)
        
        # 시장가 주문의 경우 실제 체결 가격으로 실시간 잔고 재검증
        # 주문 객체에 KRW 체결 금액 저장 (BUY/SELL 공통)
        try:
            order.krw_executed_amount = krw_order_amount
        except Exception:
            pass

        if order.order_type == OrderType.BUY:
            # 환율 정보 업데이트 (해외자산의 경우)
            if order.currency != 'KRW':
                order.exchange_rate = exchange_rate
            
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
            # 매도: 실행 직전 보유 수량 재검증(자기 자신 주문 제외)
            self._assert_sell_quantity_available(
                user_id=order.user_id,
                product_code=self._get_product_code(order),
                requested_quantity=order.quantity,
                price=order.order_price or Decimal('0'),
                exclude_order_id=order.id,
                currency=order.currency or 'KRW',
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
        
        # execution에도 KRW 환산 정보 설정 (통화와 무관하게 설정)
        try:
            rate_for_exec = order.exchange_rate or (Decimal('1.0') if (order.currency or 'KRW') == 'KRW' else exchange_rate)
            if hasattr(execution, 'exchange_rate'):
                execution.exchange_rate = rate_for_exec
            if hasattr(execution, 'krw_execution_price'):
                execution.krw_execution_price = current_price * rate_for_exec
            if hasattr(execution, 'krw_execution_amount'):
                execution.krw_execution_amount = order.quantity * (current_price * rate_for_exec)
        except Exception:
            pass

        # 체결시 손익이 얼마인지 계산
        realized_profit_loss, krw_realized_profit_loss = self._calculate_realized_profit_loss(order, execution)
        logging.info(f"체결시 손익이 얼마인지 계산 >> Realized Profit Loss: {realized_profit_loss}, KRW: {krw_realized_profit_loss}")
        logging.info(f"체결시 손익이 얼마인지 계산 >> Execution: {execution}")

        
        # 거래 내역을 먼저 생성하여 cash_before/after를 정확히 기록
        transaction = self._create_transaction_for_execution(order, execution, realized_profit_loss, krw_realized_profit_loss)
        self._update_virtual_balance_for_execution(order, execution)
        self._update_portfolio_for_execution(order, execution, transaction)


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
        if order.order_type == OrderType.BUY:
            # 금액 단위 통일: KRW 기준으로 실행 금액 산정
            if (order.currency or 'KRW') == 'KRW':
                executed_amount_krw = execution.execution_amount
            else:
                executed_amount_krw = getattr(execution, 'krw_execution_amount', None)
                if executed_amount_krw is None and order.exchange_rate:
                    executed_amount_krw = execution.execution_amount * order.exchange_rate
                executed_amount_krw = executed_amount_krw or Decimal('0')

            actual_commission_krw = Decimal('0')  # 현재 수수료 0 정책
            actual_tax_krw = Decimal('0')         # 매수 시 세금 없음
            actual_for_executed_krw = executed_amount_krw + actual_commission_krw + actual_tax_krw

            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)

            # LIMIT: 예약환불(실행분) + 실제 결제 차감
            # MARKET: 예약 없음 → 실제 결제만큼 가용/현금 동시 차감
            previous_cash = virtual_balance.cash_balance

            if order.order_method == OrderMethod.LIMIT:
                # 예약 단가: 주문 시점 원화 주문가 사용
                per_unit_reserved_krw = order.krw_order_price or order.order_price or Decimal('0')
                reserved_for_executed_krw = per_unit_reserved_krw * execution.execution_quantity
                difference = reserved_for_executed_krw - actual_for_executed_krw
                virtual_balance.available_cash += difference
            else:
                # 시장가 매수: 사전 예약 없음 → 실제 결제만큼 가용 현금도 감소
                virtual_balance.available_cash -= actual_for_executed_krw

            # 현금 잔고는 실제 결제금액만큼 감소
            virtual_balance.cash_balance -= actual_for_executed_krw
            # 매수 시 투자금액 증가 (체결금액만큼)
            virtual_balance.invested_amount = (virtual_balance.invested_amount or Decimal('0')) + executed_amount_krw
            # 마지막 거래일 업데이트
            virtual_balance.last_trade_date = datetime.now()
            virtual_balance.last_updated_at = datetime.now()
            # 이력 기록 (BUY)
            try:
                self.virtual_balance_repository._add_balance_history(
                    virtual_balance_id=virtual_balance.id,
                    previous_cash=previous_cash,
                    new_cash=virtual_balance.cash_balance,
                    change_amount=-actual_for_executed_krw,
                    change_type='BUY',
                    related_order_id=order.id,
                    description=f"BUY executed: {execution.execution_quantity} @ {execution.execution_price}, {actual_for_executed_krw}원"
                )
            except Exception:
                pass

        elif order.order_type == OrderType.SELL:
            # 매도: 실행 금액에서 수수료/세금 차감한 순입금 처리 (항상 KRW 기준)
            if (order.currency or 'KRW') == 'KRW':
                executed_amount_krw = execution.execution_amount
                commission_krw = execution.execution_fee or Decimal('0')
            else:
                rate = order.exchange_rate or self.toss_proxy_service.get_exchange_rate(order.currency)
                executed_amount_krw = getattr(execution, 'krw_execution_amount', None)
                if executed_amount_krw is None:
                    executed_amount_krw = (execution.execution_amount or Decimal('0')) * rate
                commission_krw = (execution.execution_fee or Decimal('0')) * rate

            tax_krw = self._calculate_tax(executed_amount_krw, order.order_type)
            net_amount_krw = executed_amount_krw - commission_krw - tax_krw

            virtual_balance = self.virtual_balance_repository.get_by_user_id(order.user_id)
            previous_cash = virtual_balance.cash_balance
            virtual_balance.cash_balance += net_amount_krw
            virtual_balance.available_cash += net_amount_krw
            # 매도 시 투자금액 감소 (매도한 종목의 원가만큼)
            # 포트폴리오에서 매도 수량에 해당하는 원가 계산
            portfolio = self.portfolio_repository.get_by_user_and_stock(order.user_id, self._get_product_code(order))
            if portfolio:
                # 매도 수량에 대한 원가 계산 (KRW 기준)
                if portfolio.krw_average_price:
                    sold_cost_krw = portfolio.krw_average_price * execution.execution_quantity
                elif portfolio.average_price:
                    # KRW 평균가가 없으면 현재 환율로 계산
                    if order.currency and order.currency != 'KRW':
                        rate = order.exchange_rate or self.toss_proxy_service.get_exchange_rate(order.currency)
                        sold_cost_krw = portfolio.average_price * execution.execution_quantity * rate
                    else:
                        sold_cost_krw = portfolio.average_price * execution.execution_quantity
                else:
                    sold_cost_krw = Decimal('0')
                
                virtual_balance.invested_amount = max(Decimal('0'), 
                    (virtual_balance.invested_amount or Decimal('0')) - sold_cost_krw)
            # 마지막 거래일 업데이트
            virtual_balance.last_trade_date = datetime.now()
            virtual_balance.last_updated_at = datetime.now()
            # 이력 기록 (SELL)
            try:
                self.virtual_balance_repository._add_balance_history(
                    virtual_balance_id=virtual_balance.id,
                    previous_cash=previous_cash,
                    new_cash=virtual_balance.cash_balance,
                    change_amount=net_amount_krw,
                    change_type='SELL',
                    related_order_id=order.id,
                    description=f"SELL executed: {execution.execution_quantity} @ {execution.execution_price}, {net_amount_krw}원"
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

    def _update_portfolio_for_execution(self, order: Order, execution, transaction: Transaction) -> None:
        """
        체결에 따라 포트폴리오를 업데이트합니다.
        - BUY: 수량 및 평단가 업데이트 또는 신규 생성
        - SELL: 수량 감소 및 평단가 재계산, 누적 실현손익 업데이트
        """
        user_id = order.user_id
        stock_id = self._get_product_code(order)
        quantity = execution.execution_quantity
        price = execution.execution_price
        
        # 기존 포트폴리오 조회
        portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, stock_id)
        
        if order.order_type == OrderType.BUY:
            if portfolio:
                # 기존 포트폴리오가 있는 경우 매수 업데이트
                # 원화 가격 계산 (해외자산의 경우 환율 적용)
                krw_price = None
                if order.currency and order.currency != 'KRW' and order.exchange_rate:
                    krw_price = price * order.exchange_rate
                elif order.currency == 'KRW' or not order.currency:
                    krw_price = price
                
                self.portfolio_repository.update_portfolio_buy(portfolio, quantity, price, krw_price)
            else:
                # 새로운 포트폴리오 생성 (상품/환율 정보 포함)
                average_exchange_rate = None
                krw_average_price = None
                if order.currency and order.currency != 'KRW' and order.exchange_rate:
                    try:
                        average_exchange_rate = order.exchange_rate
                        krw_average_price = (price or Decimal('0')) * order.exchange_rate
                    except Exception:
                        average_exchange_rate = None
                        krw_average_price = None

                portfolio = self.portfolio_repository.create_portfolio(
                    user_id=user_id,
                    product_code=stock_id,
                    quantity=quantity,
                    average_price=price,
                    product_name=getattr(order, 'product_name', None) or stock_id,
                    market=getattr(order, 'market', None) or 'UNKNOWN',
                    base_currency=getattr(order, 'currency', None),
                    average_exchange_rate=average_exchange_rate,
                    krw_average_price=krw_average_price,
                    industry_code=getattr(order, 'industry_code', None),
                    industry_display=getattr(order, 'industry_display', None),
                )
            order.portfolio_id = portfolio.id
                
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

                logging.info(f">> Transaction: {transaction}")
                logging.info(f">> Portfolio: {portfolio}")

                # 누적 실현 손익 업데이트
                if transaction and transaction.realized_profit_loss is not None:
                    portfolio.realized_profit_loss = (portfolio.realized_profit_loss or 0) + transaction.realized_profit_loss
                if transaction and transaction.krw_realized_profit_loss is not None:
                    portfolio.krw_realized_profit_loss = (portfolio.krw_realized_profit_loss or 0) + transaction.krw_realized_profit_loss

                logging.info(f">> Portfolio: {portfolio}")

                # 포트폴리오 업데이트 (매도)
                self.portfolio_repository.update_portfolio_sell(portfolio, quantity, price)
                order.portfolio_id = portfolio.id
                
                # 보유 수량이 0이 되면 포트폴리오 삭제
                if portfolio.current_quantity == 0:
                    self.portfolio_repository.delete_empty_portfolio(portfolio)
            else:
                logging.warning(f"매도 주문에 대한 포트폴리오를 찾을 수 없습니다: user_id={user_id}, product_code={stock_id}")
                # 포트폴리오가 없는 매도 주문은 로깅만 하고 넘어감 (데이터 정합성 문제 가능성)
        
        logging.info(f"Portfolio updated for execution: {order.id}, {order.order_type.value} {quantity} shares at {price}")

    def _create_transaction_for_execution(
        self, 
        order: Order, 
        execution, 
        realized_profit_loss: Optional[Decimal] = None,
        krw_realized_profit_loss: Optional[Decimal] = None
    ) -> Transaction:
        """체결에 따라 거래 내역을 생성합니다."""
        from app.db.models.transaction import TransactionType
        
        # 거래 유형 변환
        transaction_type = TransactionType.BUY if order.order_type == OrderType.BUY else TransactionType.SELL
        
        # 거래 내역 생성
        notes = f"Order execution for {order.id}"
        
        # execution 객체에서 krw_execution_amount 값을 가져오도록 시도
        krw_execution_amount = getattr(execution, 'krw_execution_amount', None)

        return self.transaction_service.create_transaction_from_order(
            order=order,
            transaction_type=transaction_type,
            amount=execution.execution_amount,
            price=execution.execution_price,
            quantity=execution.execution_quantity,
            commission=order.commission,
            tax=order.tax,
            notes=notes,
            currency=order.currency,
            exchange_rate=order.exchange_rate,
            krw_execution_amount=krw_execution_amount,
            realized_profit_loss=realized_profit_loss,
            krw_realized_profit_loss=krw_realized_profit_loss,
        )

    # ==================== 헬퍼 메서드들 ====================

    def _get_product_code(self, order_or_data) -> str:
        """Order 객체나 order_data에서 product_code를 추출합니다."""
        if isinstance(order_or_data, Order):
            return order_or_data.product_code or order_or_data.stock_id
        else:
            return order_or_data.get('product_code', order_or_data.get('stock_id', 'Unknown'))

    def _assert_sell_quantity_available(
        self,
        user_id: str,
        product_code: str,
        requested_quantity: Decimal,
        price: Decimal,
        exclude_order_id: Optional[str],
        currency: str = 'KRW',
    ) -> None:
        """매도 가능 수량을 검증합니다(대기/부분체결 예약 수량 반영)."""
        portfolio = self.portfolio_repository.get_by_user_and_stock(user_id, product_code)
        if not portfolio or not portfolio.is_active:
            raise ValidationError(f"해당 자산을 보유하고 있지 않습니다: {product_code}")

        reserved_quantity = self.order_repository.get_pending_sell_reserved_quantity(
            user_id, product_code, exclude_order_id=exclude_order_id
        )
        available_to_sell = portfolio.current_quantity - reserved_quantity

        # 로깅
        self._log_order_info(
            action="매도 주문 검증",
            user_id=user_id,
            product_code=product_code,
            quantity=requested_quantity,
            price=price,
            currency=currency,
        )
        logging.info(
            f"보유 수량: {portfolio.current_quantity}, 예약 수량: {reserved_quantity}, 매도 가능 수량: {available_to_sell}"
        )

        if available_to_sell < requested_quantity:
            asset_type = "주" if currency == 'KRW' else "units"
            raise ValidationError(
                f"매도 가능한 수량이 부족합니다. 요청: {requested_quantity}{asset_type}, "
                f"매도 가능: {available_to_sell}{asset_type} "
                f"(보유: {portfolio.current_quantity}{asset_type} - 예약: {reserved_quantity}{asset_type})"
            )

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

    def _calculate_realized_profit_loss(self, order: Order, execution) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """
        매도 주문 체결 시 실현손익을 계산합니다.
        
        Args:
            order: 체결된 주문 객체
            execution: 체결 정보 객체
            
        Returns:
            tuple[Optional[Decimal], Optional[Decimal]]: (현지통화 실현손익, 원화 실현손익)
            매수 주문의 경우 (None, None) 반환
        """
        # 매수 주문의 경우 실현손익 없음
        if order.order_type != OrderType.SELL:
            return None, None
            
        try:
            # 포트폴리오 조회 (평균 매수가 정보 필요)
            portfolio = self.portfolio_repository.get_by_user_and_stock(
                order.user_id, 
                self._get_product_code(order)
            )
            
            if not portfolio:
                logging.warning(f"매도 주문에 대한 포트폴리오를 찾을 수 없습니다: {order.id}")
                return Decimal('0').normalize(), Decimal('0').normalize()
            
            # 체결 정보
            execution_quantity = execution.execution_quantity
            execution_price = execution.execution_price
            average_buy_price = portfolio.average_price
            
            # 현지통화 기준 실현손익 계산
            # 실현손익 = (매도가 - 평균매수가) × 매도수량
            realized_profit_loss = (execution_price - average_buy_price) * execution_quantity
            
            # 원화 환산 실현손익 계산
            krw_realized_profit_loss = None
            
            if order.currency and order.currency != 'KRW':
                # 해외자산의 경우 환율 적용
                exchange_rate = order.exchange_rate or Decimal('1.0')
                
                # 평균 매수 시점 환율과 현재 환율 고려
                avg_exchange_rate = portfolio.average_exchange_rate or exchange_rate
                krw_avg_buy_price = portfolio.krw_average_price or (average_buy_price * avg_exchange_rate)
                krw_execution_price = execution_price * exchange_rate
                
                # 원화 기준 실현손익 = (원화 매도가 - 원화 평균매수가) × 매도수량
                krw_realized_profit_loss = (krw_execution_price - krw_avg_buy_price) * execution_quantity
            else:
                # 국내자산의 경우 현지통화와 원화가 동일
                krw_realized_profit_loss = realized_profit_loss
            
            logging.info(
                f"실현손익 계산 완료 - 종목: {self._get_product_code(order)}, "
                f"매도수량: {execution_quantity}, "
                f"매도가: {execution_price} {order.currency or 'KRW'}, "
                f"평균매수가: {average_buy_price} {order.currency or 'KRW'}, "
                f"실현손익: {realized_profit_loss} {order.currency or 'KRW'}"
                f"{f', 원화 실현손익: {krw_realized_profit_loss} KRW' if krw_realized_profit_loss != realized_profit_loss else ''}"
            )
            
            return realized_profit_loss.normalize(), krw_realized_profit_loss.normalize()
            
        except Exception as e:
            logging.error(f"실현손익 계산 중 오류 발생: {str(e)}")
            return Decimal('0').normalize(), Decimal('0').normalize()
