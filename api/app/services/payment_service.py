from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Union

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
