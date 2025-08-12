from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, asc, and_, or_
from sqlalchemy.orm import Session

from app.db.repositories.base_repository import BaseRepository
from app.db.models.order import Order, OrderExecution, OrderStatus, OrderType, OrderMethod
from app.db.models.transaction import Transaction, TransactionType


class OrderRepository(BaseRepository):
    """주문 관련 데이터베이스 작업을 처리하는 리포지토리"""

    def __init__(self, session: Session):
        super().__init__(session)

    def create_order(self, order_data: Dict[str, Any]) -> Order:
        """새로운 주문을 생성합니다."""
        order = Order(**order_data)
        self.session.add(order)
        self.session.flush()
        return order

    def get_by_user_and_id(self, user_id: str, order_id: str) -> Optional[Order]:
        """사용자별 주문을 조회합니다."""
        return self.session.query(Order).filter(
            and_(Order.user_id == user_id, Order.id == order_id)
        ).first()

    def get_orders_by_user(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        status: Optional[OrderStatus] = None,
        order_type: Optional[OrderType] = None,
        stock_id: Optional[str] = None
    ) -> List[Order]:
        """사용자의 주문 목록을 조회합니다."""
        query = self.session.query(Order).filter(Order.user_id == user_id)
        
        if status:
            query = query.filter(Order.order_status == status)
        if order_type:
            query = query.filter(Order.order_type == order_type)
        if stock_id:
            query = query.filter(Order.stock_id == stock_id)
        
        offset = (page - 1) * size
        return query.order_by(desc(Order.created_at)).offset(offset).limit(size).all()

    def count_orders_by_user(
        self,
        user_id: str,
        status: Optional[OrderStatus] = None,
        order_type: Optional[OrderType] = None,
        stock_id: Optional[str] = None
    ) -> int:
        """사용자의 주문 개수를 조회합니다."""
        query = self.session.query(Order).filter(Order.user_id == user_id)
        
        if status:
            query = query.filter(Order.order_status == status)
        if order_type:
            query = query.filter(Order.order_type == order_type)
        if stock_id:
            query = query.filter(Order.stock_id == stock_id)
        
        return query.count()

    def get_pending_orders(self, user_id: str, page: int = 1, size: int = 20) -> List[Order]:
        """대기중인 주문을 조회합니다."""
        offset = (page - 1) * size
        return self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                or_(
                    Order.order_status == OrderStatus.PENDING,
                    Order.order_status == OrderStatus.PARTIALLY_FILLED
                )
            )
        ).order_by(desc(Order.created_at)).offset(offset).limit(size).all()

    def count_pending_orders(self, user_id: str) -> int:
        """대기중인 주문 개수를 조회합니다."""
        return self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                or_(
                    Order.order_status == OrderStatus.PENDING,
                    Order.order_status == OrderStatus.PARTIALLY_FILLED
                )
            )
        ).count()

    def get_order_history(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Order]:
        """주문 이력을 조회합니다."""
        query = self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                or_(
                    Order.order_status == OrderStatus.FILLED,
                    Order.order_status == OrderStatus.CANCELLED,
                    Order.order_status == OrderStatus.REJECTED,
                    Order.order_status == OrderStatus.EXPIRED
                )
            )
        )
        
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        
        offset = (page - 1) * size
        return query.order_by(desc(Order.created_at)).offset(offset).limit(size).all()

    def count_order_history(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """주문 이력 개수를 조회합니다."""
        query = self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                or_(
                    Order.order_status == OrderStatus.FILLED,
                    Order.order_status == OrderStatus.CANCELLED,
                    Order.order_status == OrderStatus.REJECTED,
                    Order.order_status == OrderStatus.EXPIRED
                )
            )
        )
        
        if start_date:
            query = query.filter(Order.created_at >= start_date)
        if end_date:
            query = query.filter(Order.created_at <= end_date)
        
        return query.count()

    def get_order_summary(self, user_id: str, period_days: int = 30) -> Dict[str, Any]:
        """주문 요약 정보를 조회합니다."""
        start_date = datetime.now() - timedelta(days=period_days)
        
        orders = self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                Order.created_at >= start_date
            )
        ).all()
        
        summary = {
            "total_orders": len(orders),
            "pending_orders": len([o for o in orders if o.order_status == OrderStatus.PENDING]),
            "filled_orders": len([o for o in orders if o.order_status == OrderStatus.FILLED]),
            "cancelled_orders": len([o for o in orders if o.order_status == OrderStatus.CANCELLED]),
            "total_buy_amount": sum(o.executed_amount for o in orders if o.order_type == OrderType.BUY and o.order_status == OrderStatus.FILLED),
            "total_sell_amount": sum(o.executed_amount for o in orders if o.order_type == OrderType.SELL and o.order_status == OrderStatus.FILLED),
            "total_commission": sum(o.commission for o in orders if o.order_status == OrderStatus.FILLED)
        }
        
        return summary

    def update_order(self, order: Order, update_data: Dict[str, Any]) -> Order:
        """주문을 수정합니다."""
        for key, value in update_data.items():
            if hasattr(order, key) and value is not None:
                setattr(order, key, value)
        
        order.updated_at = datetime.now()
        self.session.flush()
        return order

    def cancel_order(self, order: Order, cancel_reason: Optional[str] = None) -> Order:
        """주문을 취소합니다."""
        order.order_status = OrderStatus.CANCELLED
        order.cancelled_date = datetime.now()
        if cancel_reason:
            order.notes = f"{order.notes or ''}\n취소 사유: {cancel_reason}".strip()
        
        self.session.flush()
        return order

    def execute_order(
        self,
        order: Order,
        execution_price: Decimal,
        execution_quantity: Decimal,
        commission: Decimal = Decimal('0'),
        tax: Decimal = Decimal('0')
    ) -> OrderExecution:
        """주문을 체결합니다."""
        execution_amount = execution_price * execution_quantity
        
        # 체결 내역 생성
        execution = OrderExecution(
            order_id=order.id,
            execution_price=execution_price,
            execution_quantity=execution_quantity,
            execution_amount=execution_amount,
            execution_time=datetime.now(),
            execution_fee=commission
        )
        self.session.add(execution)
        
        # 주문 정보 업데이트
        order.executed_quantity += execution_quantity
        order.executed_amount += execution_amount
        order.commission += commission
        order.tax += tax
        order.total_fee = order.commission + order.tax
        
        # 평균 체결가 계산
        if order.executed_quantity > 0:
            order.average_price = order.executed_amount / order.executed_quantity
        
        # 주문 상태 업데이트
        if order.executed_quantity >= order.quantity:
            order.order_status = OrderStatus.FILLED
            order.executed_date = datetime.now()
        elif order.executed_quantity > 0:
            order.order_status = OrderStatus.PARTIALLY_FILLED
        
        order.updated_at = datetime.now()
        
        self.session.flush()
        return execution

    def can_modify_order(self, order: Order) -> bool:
        """주문 수정 가능 여부를 확인합니다."""
        return order.order_status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]

    def can_cancel_order(self, order: Order) -> bool:
        """주문 취소 가능 여부를 확인합니다."""
        return order.order_status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]

    def get_orders_with_executions(self, user_id: str, order_ids: Optional[List[str]] = None) -> List[Order]:
        """체결 내역을 포함한 주문을 조회합니다."""
        query = self.session.query(Order).filter(Order.user_id == user_id)
        
        if order_ids:
            query = query.filter(Order.id.in_(order_ids))
        
        return query.all()

    def get_pending_sell_reserved_quantity(self, user_id: str, stock_id: str, exclude_order_id: Optional[str] = None) -> Decimal:
        """대기중/부분체결 SELL 주문들의 남은 수량 합계를 반환합니다.
        exclude_order_id가 주어지면 해당 주문은 계산에서 제외합니다.
        """
        query = self.session.query(Order).filter(
            and_(
                Order.user_id == user_id,
                Order.stock_id == stock_id,
                Order.order_type == OrderType.SELL,
                or_(
                    Order.order_status == OrderStatus.PENDING,
                    Order.order_status == OrderStatus.PARTIALLY_FILLED
                )
            )
        )
        if exclude_order_id:
            query = query.filter(Order.id != exclude_order_id)
        pending_orders = query.all()
        reserved = Decimal('0')
        for o in pending_orders:
            remaining = (o.quantity - o.executed_quantity)
            if remaining > 0:
                reserved += remaining
        return reserved
