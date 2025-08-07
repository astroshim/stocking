from datetime import datetime
from typing import ClassVar, Set, Dict, Any

from pydantic import BaseModel, field_validator

class InitVarModel(BaseModel):
    """
    향상된 기능을 가진 기본 모델:
    1. datetime 객체를 타임스탬프로 변환
    2. 타임스탬프 필드의 None 값을 0으로 변환
    3. 특정 필드에 기본값 제공
    """
    # 타임스탬프 필드 목록 (자식 클래스에서 정의)
    _timestamp_fields: ClassVar[Set[str]] = set()

    # 기본값 설정 (자식 클래스에서 정의)
    _default_values: ClassVar[Dict[str, Any]] = {}

    model_config = {
        "from_attributes": True
    }

    @field_validator('*', mode='before')
    @classmethod
    def process_values(cls, value, info):
        """값 전처리 통합 메서드"""
        field_name = info.field_name

        # 1. datetime 변환
        if isinstance(value, datetime):
            return int(value.timestamp())

        # 2. None 값 처리
        if value is None:
            # 명시적 기본값
            if field_name in cls._default_values:
                return cls._default_values[field_name]
            # 타임스탬프 필드 기본값
            elif field_name in cls._timestamp_fields:
                return 0

        return value