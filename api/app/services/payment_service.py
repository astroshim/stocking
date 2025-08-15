from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Union
import os
import json

from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.virtual_balance import VirtualBalance
from app.db.models.payment_status import PaymentStatus
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.utils.transaction_manager import TransactionManager
from app.exceptions.custom_exceptions import APIException


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.virtual_balance_repository = VirtualBalanceRepository(db)
        # PortOne V2 설정
        from app.config import config
        self._store_id = config.PORTONE_STORE_ID
        # 기본 채널키는 프론트에서 선택 가능하나, 서버 저장/주입도 가능
        self._channel_key = os.environ.get('PORTONE_CHANNEL_KEY', 'channel-key')
        self._v2_api_secret = config.PORTONE_V2_API_SECRET

    def deposit_virtual_balance(self, user_id: str, amount: Decimal, description: Optional[str] = None) -> VirtualBalance:
        """
        가상 거래 잔고에 입금합니다.

        Args:
            user_id: 사용자 ID
            amount: 입금할 금액
            description: 입금 설명

        Returns:
            업데이트된 가상 잔고 정보
        """
        with TransactionManager.transaction(self.db):
            # 금액 검증
            if amount is None or amount <= 0:
                raise APIException(status_code=400, message="입금 금액은 0보다 커야 합니다.")
            # 사용자 존재 확인
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise APIException(status_code=404, message="User not found")

            # 가상 잔고에 입금
            virtual_balance = self.virtual_balance_repository.deposit_cash(
                user_id=user_id,
                amount=amount,
                description=description or "가상 거래 잔고 입금"
            )

            return virtual_balance

    def withdraw_virtual_balance(self, user_id: str, amount: Decimal, description: Optional[str] = None) -> VirtualBalance:
        """가상 거래 잔고에서 출금합니다."""
        with TransactionManager.transaction(self.db):
            # 금액 검증
            if amount is None or amount <= 0:
                raise APIException(status_code=400, message="출금 금액은 0보다 커야 합니다.")

            # 사용자 존재 확인
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise APIException(status_code=404, message="User not found")

            try:
                virtual_balance = self.virtual_balance_repository.withdraw_cash(
                    user_id=user_id,
                    amount=amount,
                    description=description or "가상 거래 잔고 출금"
                )
                return virtual_balance
            except ValueError as e:
                if "not found" in str(e):
                    raise APIException(status_code=404, message="Virtual balance not found")
                elif "Insufficient" in str(e):
                    raise APIException(status_code=400, message="Insufficient virtual balance")
                else:
                    raise APIException(status_code=400, message=str(e))

    def get_virtual_balance(self, user_id: str) -> Optional[VirtualBalance]:
        """
        사용자의 가상 거래 잔고를 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            가상 잔고 정보
        """
        return self.virtual_balance_repository.get_by_user_id(user_id)

    def initialize_virtual_balance(self, user_id: str, initial_amount: Decimal = Decimal('1000000')) -> VirtualBalance:
        """
        새 사용자의 가상 거래 잔고를 초기화합니다.

        Args:
            user_id: 사용자 ID
            initial_amount: 초기 잔고 금액 (기본값: 1,000,000원)

        Returns:
            생성된 가상 잔고 정보
        """
        with TransactionManager.transaction(self.db):
            # 사용자 존재 확인
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise APIException(status_code=404, message="User not found")

            # 이미 가상 잔고가 있는지 확인
            existing_balance = self.virtual_balance_repository.get_by_user_id(user_id)
            if existing_balance:
                raise APIException(status_code=400, message="Virtual balance already exists")

            # 새 가상 잔고 생성
            virtual_balance = self.virtual_balance_repository.create_user_balance(
                user_id=user_id,
                initial_cash=initial_amount
            )

            return virtual_balance




    def handle_payment_callback(
        self, 
        payment_id: str, 
        status: PaymentStatus, 
        user_id: Optional[str] = None,
        amount: Optional[Decimal] = None,
        transaction_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_time: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        결제사로부터 받은 콜백을 처리합니다.

        Args:
            payment_id: 결제 ID
            status: 결제 상태
            user_id: 사용자 ID (선택적)
            amount: 결제 금액 (선택적)
            transaction_id: 결제사 거래 ID (선택적)
            payment_method: 결제 방법 (선택적)
            payment_time: 결제 시간 (선택적)
            extra_data: 추가 데이터 (선택적)

        Returns:
            처리 결과
        """
        with TransactionManager.transaction(self.db):
            result = {
                "payment_id": payment_id,
                "status": status.value,
                "processed": False,
                "message": ""
            }

            # 일반 결제(잔액 충전 등)인 경우
            if user_id and amount:
                user = self.user_repository.get_by_id(user_id)
                if user:
                    # 결제가 완료된 경우 가상 잔고 충전
                    if status == PaymentStatus.PAID:
                        try:
                            # VirtualBalance 시스템으로 충전
                            virtual_balance = self.virtual_balance_repository.deposit_cash(
                                user_id=user_id,
                                amount=amount,
                                description=f"결제 완료 입금 (ID: {payment_id})"
                            )
                            result["processed"] = True
                            result["message"] = "Virtual balance charged successfully"
                            result["virtual_balance"] = {
                                "cash_balance": float(virtual_balance.cash_balance),
                                "total_asset_value": float(virtual_balance.total_asset_value)
                            }
                        except Exception as e:
                            result["message"] = f"Failed to charge virtual balance: {str(e)}"
                    else:
                        result["message"] = f"Payment status is {status.value}, no action taken"
                else:
                    result["message"] = "User not found"
            else:
                result["message"] = "Insufficient information provided"

            return result

    # ===== PortOne V2 연동 유틸 =====
    def prepare_portone_payment(self, user_id: str, amount: Decimal, order_name: str, currency: str = "KRW") -> Dict[str, Any]:
        if amount is None or amount <= 0:
            raise APIException(status_code=400, message="결제 금액은 0보다 커야 합니다.")
        # paymentId는 클라이언트에서 채번해도 되지만, 서버에서 생성해서 내려주면 멱등성/검증이 용이
        from uuid import uuid4
        payment_id = uuid4().hex
        return {
            "store_id": self._store_id,
            "channel_key": self._channel_key,
            "payment_id": payment_id,
            "order_name": order_name,
            "amount": amount,
            "currency": currency,
        }

    def complete_portone_payment(self, payment_id: str) -> Dict[str, Any]:
        try:
            import portone_server_sdk as portone
            client = portone.PaymentClient(secret=self._v2_api_secret)
            p = client.get_payment(payment_id=payment_id)
        except Exception as e:
            raise APIException(status_code=400, message=f"결제 조회 실패: {str(e)}")

        # 승인 상태만 통과
        import portone_server_sdk as portone
        if not isinstance(p, portone.payment.PaidPayment):
            raise APIException(status_code=400, message="결제가 승인되지 않았습니다.")

        # 비즈니스 검증 (custom_data 등)
        try:
            custom = json.loads(p.custom_data) if getattr(p, 'custom_data', None) else {}
        except Exception:
            custom = {}

        # TODO: 주문 조회/금액 일치 검증 로직 연결 가능
        return {
            "status": "PAID",
            "payment_id": payment_id,
            "amount": float(p.amount.total),
            "currency": p.currency,
        }
