from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

from app.utils.simple_paging import SimplePage

T = TypeVar('T')

class PaginationMeta(BaseModel):
    """페이징 메타데이터"""
    page: int
    per_page: int
    has_next: bool
    next_page: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class PagedResponse(BaseModel, Generic[T]):
    """페이징된 응답의 기본 구조"""
    items: List[T]
    pagination: PaginationMeta

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_page_result(cls, page: SimplePage[T]):
        """
        페이징 결과 객체로부터 응답 생성

        Args:
            items_list: 변환된 아이템 리스트
            page_result: 페이징 결과 객체
        """
        return cls(
            items=page.items,
            pagination=PaginationMeta(
                page=page.page,
                per_page=page.per_page,
                has_next=page.has_next,
                next_page=page.page + 1 if page.has_next else None
            )
        )