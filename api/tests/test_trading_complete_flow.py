import pytest
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.db import Base
from app.db.models.user import User
from app.db.models.transaction import Transaction, TransactionType
from app.db.models.order import Order, OrderType, OrderMethod, OrderStatus
from app.db.models.portfolio import Portfolio
from app.db.models.virtual_balance import VirtualBalance, VirtualBalanceHistory
from app.db.repositories.order_repository import OrderRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.transaction_repository import TransactionRepository
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.transaction_service import TransactionService
class FakeTossProxyService:
    def get_stock_price_details(self, product_code: str):
        return {"result": [{"close": 50000.0, "currency": "KRW"}]}

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


@pytest.fixture()
def session():
    """테스트용 인메모리 데이터베이스 세션"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user_with_balance(db, initial_cash: Decimal = Decimal('1000000')):
    """테스트용 사용자와 초기 잔고 생성"""
    user = User(userid='test_user', email='test@example.com', password='pw', name='Tester')
    db.add(user)
    db.flush()

    vb_repo = VirtualBalanceRepository(db)
    vb_repo.create_user_balance(user.id, initial_cash)
    db.commit()
    return user


class TestCompleteTradeFlow:
    """거래 전체 플로우에 대한 통합 테스트"""

    def test_deposit_updates_balance_and_history(self, session):
        """입금 시 잔고와 이력이 정확히 업데이트되는지 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        payment_service = PaymentService(session)
        vb_repo = VirtualBalanceRepository(session)
        
        # 초기 상태 확인
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('1000000')
        assert vb.available_cash == Decimal('1000000')
        assert vb.invested_amount == Decimal('0')
        
        # 50만원 입금
        deposit_amount = Decimal('500000')
        payment_service.deposit_virtual_balance(
            user_id=user.id,
            amount=deposit_amount,
            description='추가 입금 테스트'
        )
        
        # 입금 후 잔고 확인
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('1500000')
        assert vb.available_cash == Decimal('1500000')
        
        # 입금 거래 내역 확인
        tx_service = TransactionService(session)
        tx = tx_service.create_deposit_transaction(
            user_id=user.id,
            amount=deposit_amount,
            description='추가 입금 거래내역'
        )
        assert tx.transaction_type == TransactionType.DEPOSIT
        assert tx.amount == deposit_amount
        assert tx.cash_balance_before == Decimal('1500000')
        assert tx.cash_balance_after == Decimal('2000000')
        
        # 잔고 이력 확인
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) >= 2  # 초기 생성 + 입금
        
        # 가장 최근 이력 (입금)
        latest_history = histories[0]
        assert latest_history.change_type == 'DEPOSIT'
        assert latest_history.change_amount == deposit_amount
        assert latest_history.previous_cash_balance == Decimal('1000000')
        assert latest_history.new_cash_balance == Decimal('1500000')

    def test_withdraw_with_validation(self, session):
        """출금 시 잔고 검증과 이력 업데이트 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        payment_service = PaymentService(session)
        vb_repo = VirtualBalanceRepository(session)
        
        # 30만원 출금
        withdraw_amount = Decimal('300000')
        payment_service.withdraw_virtual_balance(
            user_id=user.id,
            amount=withdraw_amount,
            description='출금 테스트'
        )
        
        # 출금 후 잔고 확인
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('700000')
        assert vb.available_cash == Decimal('700000')
        
        # 출금 거래 내역 생성
        tx_service = TransactionService(session)
        tx = tx_service.create_withdraw_transaction(
            user_id=user.id,
            amount=withdraw_amount,
            description='출금 거래내역'
        )
        assert tx.transaction_type == TransactionType.WITHDRAW
        assert tx.amount == withdraw_amount
        assert tx.cash_balance_before == Decimal('700000')
        assert tx.cash_balance_after == Decimal('400000')
        
        # 잔고 이력 확인
        histories = vb_repo.get_balance_history(user.id)
        withdraw_history = next(h for h in histories if h.change_type == 'WITHDRAW')
        assert withdraw_history.change_amount == -withdraw_amount
        assert withdraw_history.previous_cash_balance == Decimal('1000000')
        assert withdraw_history.new_cash_balance == Decimal('700000')
        
        # 잔고 부족 시 출금 실패 테스트
        with pytest.raises(Exception):
            payment_service.withdraw_virtual_balance(
                user_id=user.id,
                amount=Decimal('1000000')  # 현재 잔고보다 많은 금액
            )

    def test_buy_order_complete_flow(self, session):
        """매수 주문 생성부터 체결까지 전체 플로우 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        portfolio_repo = PortfolioRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 1) 매수 주문 생성
        buy_order_data = {
            'stock_id': 'stock001',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('50000'),  # 주당 5만원
            'notes': '삼성전자 10주 매수'
        }
        buy_order = service.create_order(user.id, buy_order_data)
        
        # 주문 상태 확인
        assert buy_order.order_status == OrderStatus.PENDING
        assert buy_order.executed_quantity == Decimal('0')
        
        # 잔고 예약 확인 (10주 * 5만원 = 50만원)
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('1000000')  # 현금은 그대로
        assert vb.available_cash == Decimal('500000')  # 가용 현금은 50만원 감소
        
        # 2) 주문 체결
        execute(service, order_repo, buy_order.id, Decimal('50000'))
        
        # 체결 후 주문 상태 확인
        executed_order = session.query(Order).filter(Order.id == buy_order.id).first()
        assert executed_order.order_status == OrderStatus.FILLED
        assert executed_order.executed_quantity == Decimal('10')
        assert executed_order.average_price == Decimal('50000')
        assert executed_order.executed_amount == Decimal('500000')
        
        # 체결 후 잔고 확인
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('500000')  # 50만원 차감
        assert vb.available_cash == Decimal('500000')  # 예약 해제
        assert vb.invested_amount == Decimal('500000')  # 투자금액 증가
        assert vb.total_buy_amount == Decimal('500000')  # 총 매수금액
        
        # 포트폴리오 확인
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock001')
        assert portfolio is not None
        assert portfolio.current_quantity == 10
        assert portfolio.average_price == Decimal('50000')
        assert portfolio.first_buy_date is not None
        assert portfolio.last_buy_date is not None
        
        # 거래 내역 확인
        tx = session.query(Transaction).filter(
            Transaction.order_id == buy_order.id
        ).first()
        assert tx is not None
        assert tx.transaction_type == TransactionType.BUY
        assert tx.quantity == 10
        assert tx.price == Decimal('50000')
        assert tx.amount == Decimal('500000')
        assert tx.cash_balance_before == Decimal('1000000')
        assert tx.cash_balance_after == Decimal('500000')
        
        # 잔고 이력 확인
        histories = vb_repo.get_balance_history(user.id)
        buy_history = next(h for h in histories if h.change_type == 'BUY')
        assert buy_history.change_amount == Decimal('-500000')
        assert buy_history.related_order_id == buy_order.id

    def test_sell_order_with_profit_loss(self, session):
        """매도 주문과 실현 손익 계산 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        portfolio_repo = PortfolioRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 먼저 10주를 5만원에 매수
        buy_order = service.create_order(user.id, {
            'stock_id': 'stock001',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('50000')
        })
        execute(service, order_repo, buy_order.id, Decimal('50000'))
        
        # 포트폴리오 초기 상태 확인
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock001')
        assert portfolio.current_quantity == 10
        assert portfolio.average_price == Decimal('50000')
        assert portfolio.realized_profit_loss == Decimal('0')
        
        # 5주를 6만원에 매도 (이익 실현)
        sell_order = service.create_order(user.id, {
            'stock_id': 'stock001',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('60000')
        })
        execute(service, order_repo, sell_order.id, Decimal('60000'))
        
        # 매도 후 포트폴리오 확인
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock001')
        assert portfolio.current_quantity == 5  # 5주 남음
        assert portfolio.average_price == Decimal('50000')  # 평균가는 유지
        # 실현 손익 = (매도가 - 평균가) * 수량 = (60000 - 50000) * 5 = 50000
        assert portfolio.realized_profit_loss == Decimal('50000')
        
        # 잔고 확인
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('800000')  # 50만원 + 30만원
        assert vb.available_cash == Decimal('800000')
        assert vb.invested_amount == Decimal('250000')  # 남은 5주 * 5만원
        assert vb.total_sell_amount == Decimal('300000')  # 매도 금액
        
        # 매도 거래 내역 확인
        tx = session.query(Transaction).filter(
            Transaction.order_id == sell_order.id
        ).first()
        assert tx.transaction_type == TransactionType.SELL
        assert tx.quantity == 5
        assert tx.price == Decimal('60000')
        assert tx.amount == Decimal('300000')

    def test_multiple_buy_average_price_calculation(self, session):
        """여러 번 매수 시 평균 단가 계산 테스트"""
        user = create_user_with_balance(session, Decimal('3000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        portfolio_repo = PortfolioRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 첫 번째 매수: 10주 @ 50,000원
        order1 = service.create_order(user.id, {
            'stock_id': 'stock002',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('50000')
        })
        execute(service, order_repo, order1.id, Decimal('50000'))
        
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock002')
        assert portfolio.current_quantity == 10
        assert portfolio.average_price == Decimal('50000')
        
        # 두 번째 매수: 20주 @ 40,000원
        order2 = service.create_order(user.id, {
            'stock_id': 'stock002',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('20'),
            'order_price': Decimal('40000')
        })
        execute(service, order_repo, order2.id, Decimal('40000'))
        
        # 평균 단가 계산: (10*50000 + 20*40000) / 30 = 43,333.33...
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock002')
        assert portfolio.current_quantity == 30
        assert round(portfolio.average_price, 2) == Decimal('43333.33')
        
        # 세 번째 매수: 30주 @ 30,000원
        order3 = service.create_order(user.id, {
            'stock_id': 'stock002',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('30'),
            'order_price': Decimal('30000')
        })
        execute(service, order_repo, order3.id, Decimal('30000'))
        
        # 평균 단가 재계산: (30*43333.33 + 30*30000) / 60 = 36,666.67
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock002')
        assert portfolio.current_quantity == 60
        # 소수점 계산 오차를 고려한 검증
        expected_avg = (Decimal('30') * Decimal('43333.33') + Decimal('30') * Decimal('30000')) / Decimal('60')
        assert abs(portfolio.average_price - expected_avg) < Decimal('1')

    def test_complete_sell_and_rebuy(self, session):
        """전량 매도 후 재매수 시나리오 테스트"""
        user = create_user_with_balance(session, Decimal('2000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        portfolio_repo = PortfolioRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 10주 매수
        buy1 = service.create_order(user.id, {
            'stock_id': 'stock003',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('100000')
        })
        execute(service, order_repo, buy1.id, Decimal('100000'))
        
        # 전량 매도
        sell = service.create_order(user.id, {
            'stock_id': 'stock003',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('120000')
        })
        execute(service, order_repo, sell.id, Decimal('120000'))
        
        # 전량 매도 후 포트폴리오 확인 (삭제될 수 있음)
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock003')
        # 전량 매도 시 포트폴리오가 삭제될 수 있음
        if portfolio:
            assert portfolio.current_quantity == 0
            assert portfolio.average_price == Decimal('0')  # 전량 매도 시 평균가 초기화
            assert portfolio.realized_profit_loss == Decimal('200000')  # (120000-100000)*10
        
        # 재매수
        buy2 = service.create_order(user.id, {
            'stock_id': 'stock003',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('110000')
        })
        execute(service, order_repo, buy2.id, Decimal('110000'))
        
        # 재매수 후 포트폴리오 확인
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock003')
        assert portfolio.current_quantity == 5
        assert portfolio.average_price == Decimal('110000')  # 새로운 평균가
        # 전량 매도 시 포트폴리오가 삭제되므로 새 포트폴리오의 실현손익은 0
        assert portfolio.realized_profit_loss == Decimal('0')

    def test_balance_history_tracking(self, session):
        """모든 거래에 대한 잔고 이력 추적 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        payment_service = PaymentService(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 1. 초기 이력 확인
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) == 1
        assert histories[0].change_type == 'INITIAL_DEPOSIT'
        
        # 2. 입금
        payment_service.deposit_virtual_balance(user.id, Decimal('500000'))
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) == 2
        assert histories[0].change_type == 'DEPOSIT'
        assert histories[0].change_amount == Decimal('500000')
        
        # 3. 매수
        buy = service.create_order(user.id, {
            'stock_id': 'stock004',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('50000')
        })
        execute(service, order_repo, buy.id, Decimal('50000'))
        
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) == 3
        assert histories[0].change_type == 'BUY'
        assert histories[0].change_amount == Decimal('-500000')
        assert histories[0].related_order_id == buy.id
        
        # 4. 매도
        sell = service.create_order(user.id, {
            'stock_id': 'stock004',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('60000')
        })
        execute(service, order_repo, sell.id, Decimal('60000'))
        
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) == 4
        assert histories[0].change_type == 'SELL'
        assert histories[0].change_amount == Decimal('300000')
        assert histories[0].related_order_id == sell.id
        
        # 5. 출금
        payment_service.withdraw_virtual_balance(user.id, Decimal('200000'))
        histories = vb_repo.get_balance_history(user.id)
        assert len(histories) == 5
        assert histories[0].change_type == 'WITHDRAW'
        assert histories[0].change_amount == Decimal('-200000')
        
        # 전체 이력의 잔고 연속성 확인
        for i in range(1, len(histories)):
            current = histories[i-1]
            previous = histories[i]
            assert current.previous_cash_balance == previous.new_cash_balance

    def test_concurrent_orders_cash_reservation(self, session):
        """동시 주문 시 현금 예약 관리 테스트"""
        user = create_user_with_balance(session, Decimal('1000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 첫 번째 매수 주문 (미체결)
        order1 = service.create_order(user.id, {
            'stock_id': 'stock005',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('40000')  # 40만원 예약
        })
        
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('1000000')
        assert vb.available_cash == Decimal('600000')  # 40만원 예약
        
        # 두 번째 매수 주문 (미체결)
        order2 = service.create_order(user.id, {
            'stock_id': 'stock006',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('50000')  # 25만원 예약
        })
        
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('1000000')
        assert vb.available_cash == Decimal('350000')  # 65만원 예약
        
        # 세 번째 매수 주문 시도 (잔고 부족)
        with pytest.raises(Exception):
            service.create_order(user.id, {
                'stock_id': 'stock007',
                'order_type': OrderType.BUY,
                'order_method': OrderMethod.LIMIT,
                'quantity': Decimal('10'),
                'order_price': Decimal('40000')  # 40만원 필요, 35만원만 가용
            })
        
        # 첫 번째 주문 체결
        execute(service, order_repo, order1.id, Decimal('40000'))
        
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('600000')  # 40만원 차감
        assert vb.available_cash == Decimal('350000')  # 예약 해제, 25만원만 예약 중
        
        # 두 번째 주문 취소
        service.cancel_order(user.id, order2.id)
        
        vb = vb_repo.get_by_user_id(user.id)
        assert vb.cash_balance == Decimal('600000')
        assert vb.available_cash == Decimal('600000')  # 모든 예약 해제

    def test_sell_order_stock_reservation(self, session):
        """매도 주문 시 보유 주식 예약 관리 테스트"""
        user = create_user_with_balance(session, Decimal('2000000'))
        
        order_repo = OrderRepository(session)
        vb_repo = VirtualBalanceRepository(session)
        portfolio_repo = PortfolioRepository(session)
        service = OrderService(order_repo, vb_repo, FakeTossProxyService())
        
        # 20주 매수
        buy = service.create_order(user.id, {
            'stock_id': 'stock008',
            'order_type': OrderType.BUY,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('20'),
            'order_price': Decimal('50000')
        })
        execute(service, order_repo, buy.id, Decimal('50000'))
        
        # 첫 번째 매도 주문 (10주, 미체결)
        sell1 = service.create_order(user.id, {
            'stock_id': 'stock008',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('10'),
            'order_price': Decimal('60000')
        })
        
        # 두 번째 매도 주문 (5주, 미체결)
        sell2 = service.create_order(user.id, {
            'stock_id': 'stock008',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('65000')
        })
        
        # 세 번째 매도 주문 시도 (초과 매도)
        with pytest.raises(Exception):
            service.create_order(user.id, {
                'stock_id': 'stock008',
                'order_type': OrderType.SELL,
                'order_method': OrderMethod.LIMIT,
                'quantity': Decimal('10'),  # 20주 중 15주는 이미 예약
                'order_price': Decimal('70000')
            })
        
        # 첫 번째 매도 체결
        execute(service, order_repo, sell1.id, Decimal('60000'))
        
        portfolio = portfolio_repo.get_by_user_and_stock(user.id, 'stock008')
        assert portfolio.current_quantity == 10  # 10주 매도 완료
        
        # 이제 5주 추가 매도 가능 (기존 5주 예약 + 5주 추가)
        sell3 = service.create_order(user.id, {
            'stock_id': 'stock008',
            'order_type': OrderType.SELL,
            'order_method': OrderMethod.LIMIT,
            'quantity': Decimal('5'),
            'order_price': Decimal('70000')
        })
        
        # 포트폴리오의 모든 주식이 예약됨
        # 추가 매도 불가
        with pytest.raises(Exception):
            service.create_order(user.id, {
                'stock_id': 'stock008',
                'order_type': OrderType.SELL,
                'order_method': OrderMethod.LIMIT,
                'quantity': Decimal('1'),
                'order_price': Decimal('75000')
            })
