from fastapi import APIRouter, Depends, status, Request

from app.api.v1.schemas.payment_schema import (
    ChargeRequest, PaymentRequest, PaymentResponse, PaymentCallbackRequest,
    VirtualBalanceDepositRequest, VirtualBalanceWithdrawRequest, 
    VirtualBalanceInitRequest, VirtualBalanceResponse
)
from app.api.v1.schemas.user_schema import ResponseUser
from app.config.di import get_payment_service
from app.config.get_current_user import get_current_user
from app.exceptions.custom_exceptions import APIException
from app.services.payment_service import PaymentService
from app.utils.response_helper import create_response

router = APIRouter()



@router.post("/process", summary="결제 처리")
def process_payment(
    payment_data: PaymentRequest,
    current_user_id: str = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    사용자의 잔액으로 결제를 처리합니다.
    """
    try:
        user = payment_service.process_payment(
            user_id=current_user_id,
            amount=payment_data.amount,
            description=payment_data.description
        )

        return create_response(
            data=ResponseUser.model_validate(user).model_dump(),
            status_code=status.HTTP_200_OK,
            message="Payment processed successfully"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to process payment",
            detail={"error": str(e)}
        )


@router.post("/callback", summary="결제 콜백 처리")
def payment_callback(
    callback_data: PaymentCallbackRequest,
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    결제사로부터 받은 콜백을 처리합니다.

    이 엔드포인트는 결제사에서 결제 상태 업데이트를 받아 처리합니다.
    결제 완료, 실패, 취소 등의 상태 변경을 처리할 수 있습니다.
    """
    try:
        result = payment_service.handle_payment_callback(
            payment_id=callback_data.payment_id,
            status=callback_data.status,
            user_id=callback_data.user_id,
            amount=callback_data.amount,
            transaction_id=callback_data.transaction_id,
            payment_method=callback_data.payment_method,
            payment_time=callback_data.payment_time,
            extra_data=callback_data.extra_data
        )

        return create_response(
            data=result,
            status_code=status.HTTP_200_OK,
            message="Payment callback processed"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to process payment callback",
            detail={"error": str(e)}
        )


# === 가상 거래 잔고 관련 엔드포인트 ===

@router.post("/virtual-balance/deposit", response_model=VirtualBalanceResponse, summary="가상 잔고 입금")
def deposit_virtual_balance(
    deposit_data: VirtualBalanceDepositRequest,
    current_user_id: str = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    가상 거래 잔고에 입금합니다.
    실제 결제 시스템과 연동하여 입금 처리됩니다.
    """
    try:
        virtual_balance = payment_service.deposit_virtual_balance(
            user_id=current_user_id,
            amount=deposit_data.amount,
            description=deposit_data.description
        )

        return create_response(
            data=VirtualBalanceResponse.model_validate(virtual_balance).model_dump(),
            status_code=status.HTTP_200_OK,
            message="Virtual balance deposit successful"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to deposit virtual balance",
            detail={"error": str(e)}
        )


@router.post("/virtual-balance/withdraw", response_model=VirtualBalanceResponse, summary="가상 잔고 출금")
def withdraw_virtual_balance(
    withdraw_data: VirtualBalanceWithdrawRequest,
    current_user_id: str = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    가상 거래 잔고에서 출금합니다.
    """
    try:
        virtual_balance = payment_service.withdraw_virtual_balance(
            user_id=current_user_id,
            amount=withdraw_data.amount,
            description=withdraw_data.description
        )

        return create_response(
            data=VirtualBalanceResponse.model_validate(virtual_balance).model_dump(),
            status_code=status.HTTP_200_OK,
            message="Virtual balance withdrawal successful"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to withdraw virtual balance",
            detail={"error": str(e)}
        )


@router.get("/virtual-balance", response_model=VirtualBalanceResponse, summary="가상 잔고 조회")
def get_virtual_balance(
    current_user_id: str = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    사용자의 가상 거래 잔고를 조회합니다.
    """
    try:
        virtual_balance = payment_service.get_virtual_balance(current_user_id)
        
        if not virtual_balance:
            raise APIException(status_code=404, message="Virtual balance not found")

        return create_response(
            data=VirtualBalanceResponse.model_validate(virtual_balance).model_dump(),
            status_code=status.HTTP_200_OK,
            message="Virtual balance retrieved successfully"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get virtual balance",
            detail={"error": str(e)}
        )


@router.post("/virtual-balance/initialize", response_model=VirtualBalanceResponse, summary="가상 잔고 초기화")
def initialize_virtual_balance(
    init_data: VirtualBalanceInitRequest,
    current_user_id: str = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service)
):
    """
    새 사용자의 가상 거래 잔고를 초기화합니다.
    """
    try:
        virtual_balance = payment_service.initialize_virtual_balance(
            user_id=current_user_id,
            initial_amount=init_data.initial_amount
        )

        return create_response(
            data=VirtualBalanceResponse.model_validate(virtual_balance).model_dump(),
            status_code=status.HTTP_201_CREATED,
            message="Virtual balance initialized successfully"
        )
    except APIException as e:
        raise e
    except Exception as e:
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to initialize virtual balance",
            detail={"error": str(e)}
        )
