from fastapi import HTTPException
from typing import Any, Dict, Optional

class APIException(HTTPException):
    """
    API 예외 기본 클래스
    """
    def __init__(
            self,
            status_code: int,
            message: Optional[str] = None,
            detail: Any = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.message = message


class ValidationError(Exception):
    """
    데이터 유효성 검증 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class NotFoundError(Exception):
    """
    리소스를 찾을 수 없음 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InsufficientBalanceError(Exception):
    """
    잔고 부족 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class PermissionDeniedError(Exception):
    """
    권한 거부 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ConflictError(Exception):
    """
    리소스 충돌 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class BusinessLogicError(Exception):
    """
    비즈니스 로직 오류
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
