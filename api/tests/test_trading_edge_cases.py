import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.db import Base
from app.db.models.user import User
from app.db.models.order import OrderType, OrderMethod
from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.services.order_service import OrderService
class FakeTossProxyService:
    def get_stock_price_details(self, product_code: str):
        return {"result": [{"close": 10000.0, "currency": "KRW"}]}

    def get_exchange_rate(self, from_currency: str, to_currency: str = 'KRW'):
        return Decimal('1300')

def execute(service: OrderService, order_repo: OrderRepository, order_id, price, executed_quantity=None, commission=Decimal('0'), tax=Decimal('0')):
    order = order_repo.get_by_id(order_id)
    if executed_quantity is None:
        executed_quantity = order.quantity - order.executed_quantity
    execution = order_repo.execute_order(order, Decimal(price), Decimal(executed_quantity), Decimal(commission), Decimal(tax))
    service._create_transaction_for_execution(order, execution)
    service._update_virtual_balance_for_execution(order, execution)
    service._update_portfolio_for_execution(order, execution)
    return execution
from app.services.payment_service import PaymentService
from app.exceptions.custom_exceptions import ValidationError, InsufficientBalanceError


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user_with_balance(db, initial_cash: Decimal = Decimal('1000000')):
    user = User(userid='test_user', email='test@example.com', password='pw', name='Tester')
    db.add(user)
    db.flush()
    vb_repo = VirtualBalanceRepository(db)
    vb_repo.create_user_balance(user.id, initial_cash)
    db.commit()
    return user


def test_prevent_oversell_with_pending_reservations(session):
    user = create_user_with_balance(session, Decimal('1000000'))
    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo, FakeTossProxyService())

    # 보유 만들기: 10주 매수 후 체결
    buy_order = service.create_order(user.id, {
        'stock_id': 'edge001',
        'order_type': OrderType.BUY,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('10000')
    })
    execute(service, order_repo, buy_order.id, Decimal('10000'))

    # 대기 SELL 6주 생성 (체결하지 않음)
    service.create_order(user.id, {
        'stock_id': 'edge001',
        'order_type': OrderType.SELL,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('6'),
        'order_price': Decimal('20000')
    })

    # 추가 SELL 5주는 과다 매도로 거부되어야 함 (남은 가능 4)
    with pytest.raises(ValidationError):
        service.create_order(user.id, {
            'stock_id': 'edge001',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('20000')
        })


def test_insufficient_cash_error_message(session):
    user = create_user_with_balance(session, Decimal('10000'))
    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)

    with pytest.raises(InsufficientBalanceError) as e:
        service.create_order(user.id, {
            'stock_id': 'edge002',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('2'),
            'order_price': Decimal('10000')
        })
    assert '잔고' in str(e.value)


def test_negative_and_zero_amount_validation_for_payments(session):
    user = create_user_with_balance(session, Decimal('100000'))
    payment_service = PaymentService(session)

    # 0원 입금 시도 -> 400
    with pytest.raises(Exception):
        payment_service.deposit_virtual_balance(user.id, Decimal('0'))

    # 음수 출금 시도 -> 400
    with pytest.raises(Exception):
        payment_service.withdraw_virtual_balance(user.id, Decimal('-1'))


