import enum


class PaymentStatus(enum.Enum):
    READY = "ready"  # 결제 전
    IN_PROGRESS = "in_progress"  # 결제 진행 중
    PAID = "paid",  # 결제 완료
    CANCELLED = "cancelled"  # 결제 취소
    FAILED = "failed"  # 결제 실패
