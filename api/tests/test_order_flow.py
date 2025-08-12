import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.db import Base
from app.db.models.user import User
from app.db.models.transaction import Transaction, TransactionType
from app.db.models.order import OrderType, OrderMethod
from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.services.order_service import OrderService


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


def test_buy_then_sell_updates_balances_and_transactions(session):
    user = create_user_with_balance(session, Decimal('1000000'))

    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)

    # 1) BUY 주문 생성 (지정가)
    buy_order_data = {
        'stock_id': 'stock001',
        'order_type': OrderType.BUY,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('10000'),
        'notes': 'buy 10 @ 10000'
    }
    buy_order = service.create_order(user.id, buy_order_data)

    vb = vb_repo.get_by_user_id(user.id)
    assert vb.cash_balance == Decimal('1000000')
    assert vb.available_cash == Decimal('900000')  # 10 * 10000 예약

    # 2) BUY 주문 체결
    service.execute_order(user.id, buy_order.id, Decimal('10000'))
    vb = vb_repo.get_by_user_id(user.id)
    assert vb.cash_balance == Decimal('900000')
    assert vb.available_cash == Decimal('900000')  # 예약 해제 후 가용=현금
    assert vb.invested_amount == Decimal('100000')

    # 거래 레코드 검증 (BUY)
    tx_buy = session.query(Transaction).filter(Transaction.order_id == buy_order.id).one()
    assert tx_buy.transaction_type == TransactionType.BUY
    assert tx_buy.amount == Decimal('100000')
    # 체결 전/후 잔고 스냅샷이 정확한지 확인
    assert tx_buy.cash_balance_before == Decimal('1000000')
    assert tx_buy.cash_balance_after == Decimal('900000')

    # 3) SELL 주문 생성 (지정가)
    sell_order_data = {
        'stock_id': 'stock001',
        'order_type': OrderType.SELL,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('5'),
        'order_price': Decimal('20000'),
        'notes': 'sell 5 @ 20000'
    }
    sell_order = service.create_order(user.id, sell_order_data)

    # 4) SELL 주문 체결
    service.execute_order(user.id, sell_order.id, Decimal('20000'))
    vb = vb_repo.get_by_user_id(user.id)
    # 매도 5주 * 20000 = 100000 순입금
    assert vb.cash_balance == Decimal('1000000')
    assert vb.available_cash == Decimal('1000000')
    assert vb.invested_amount == Decimal('0')

    # 거래 레코드 검증 (SELL)
    tx_sell = session.query(Transaction).filter(Transaction.order_id == sell_order.id).one()
    assert tx_sell.transaction_type == TransactionType.SELL
    assert tx_sell.amount == Decimal('100000')
    assert tx_sell.cash_balance_before == Decimal('900000')
    assert tx_sell.cash_balance_after == Decimal('1000000')


def test_prevent_oversell_with_pending_reservations(session):
    user = create_user_with_balance(session, Decimal('1000000'))

    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)

    # 보유 만들기: 10주 매수 후 체결
    buy_order = service.create_order(user.id, {
        'stock_id': 'stock001',
        'order_type': OrderType.BUY,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('10000')
    })
    service.execute_order(user.id, buy_order.id, Decimal('10000'))

    # 대기 SELL 6주 생성 (체결하지 않음)
    service.create_order(user.id, {
        'stock_id': 'stock001',
        'order_type': OrderType.SELL,
        'order_method': OrderMethod.LIMIT,
        'quantity': Decimal('6'),
        'order_price': Decimal('20000')
    })

    # 추가 SELL 5주는 과다 매도로 거부되어야 함 (남은 가능 4)
    with pytest.raises(Exception):
        service.create_order(user.id, {
            'stock_id': 'stock001',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('20000')
        })

