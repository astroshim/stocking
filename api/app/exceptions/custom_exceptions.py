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
