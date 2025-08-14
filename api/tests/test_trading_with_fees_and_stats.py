import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.db import Base
from app.db.models.user import User
from app.db.models.transaction import Transaction, TransactionType
from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.services.order_service import OrderService
from app.services.transaction_service import TransactionService


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


def test_buy_with_custom_commission(session):
    user = create_user_with_balance(session, Decimal('1000000'))

    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)

    order = service.create_order(user.id, {
        'stock_id': 'fee001',
        'order_type': service.order_repository.session.query.type_mapper.classname if False else  type('x', (), {}) and  __import__('app.db.models.order', fromlist=['OrderType']).OrderType.BUY,
        'order_method': __import__('app.db.models.order', fromlist=['OrderMethod']).OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('10000')
    })

    # 사용자 지정 수수료로 체결
    service.execute_order(user.id, order.id, Decimal('10000'), executed_quantity=Decimal('10'), commission=Decimal('1500'), tax=Decimal('0'))

    tx = session.query(Transaction).filter_by(order_id=order.id).one()
    assert tx.transaction_type == TransactionType.BUY
    assert tx.commission == Decimal('1500')


def test_sell_with_commission_and_tax(session):
    user = create_user_with_balance(session, Decimal('2000000'))

    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)

    buy = service.create_order(user.id, {
        'stock_id': 'fee002',
        'order_type': __import__('app.db.models.order', fromlist=['OrderType']).OrderType.BUY,
        'order_method': __import__('app.db.models.order', fromlist=['OrderMethod']).OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('100000')
    })
    service.execute_order(user.id, buy.id, Decimal('100000'), executed_quantity=Decimal('10'))

    sell = service.create_order(user.id, {
        'stock_id': 'fee002',
        'order_type': __import__('app.db.models.order', fromlist=['OrderType']).OrderType.SELL,
        'order_method': __import__('app.db.models.order', fromlist=['OrderMethod']).OrderMethod.LIMIT,
        'quantity': Decimal('10'),
        'order_price': Decimal('120000')
    })
    service.execute_order(user.id, sell.id, Decimal('120000'), executed_quantity=Decimal('10'), commission=Decimal('2000'), tax=Decimal('1000'))

    tx = session.query(Transaction).filter_by(order_id=sell.id).one()
    assert tx.transaction_type == TransactionType.SELL
    assert tx.commission == Decimal('2000')
    assert tx.tax == Decimal('1000')


def test_daily_trading_statistics(session):
    user = create_user_with_balance(session, Decimal('1000000'))

    order_repo = OrderRepository(session)
    vb_repo = VirtualBalanceRepository(session)
    service = OrderService(order_repo, vb_repo)
    ts = TransactionService(session)

    order = service.create_order(user.id, {
        'stock_id': 'stat001',
        'order_type': __import__('app.db.models.order', fromlist=['OrderType']).OrderType.BUY,
        'order_method': __import__('app.db.models.order', fromlist=['OrderMethod']).OrderMethod.LIMIT,
        'quantity': Decimal('5'),
        'order_price': Decimal('10000')
    })
    service.execute_order(user.id, order.id, Decimal('10000'))

    ts.update_daily_statistics(user.id)


