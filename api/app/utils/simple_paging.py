from typing import List, TypeVar, Generic, Optional

T = TypeVar('T')

class SimplePage(Generic[T]):
    def __init__(self, items: List[T], page: int, per_page: int, has_next: bool = None):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.has_next = has_next

    @property
    def next_offset(self) -> Optional[int]:
        """다음 페이지의 오프셋을 계산"""
        if self.has_next:
            return self.page + self.per_page
        return None

def paginate_without_count(
        query,
        page: int,
        per_page: int = 0
) -> SimplePage:
    """
    COUNT(*) 쿼리 없이 페이징 처리하는 함수

    :param query: 페이징할 쿼리 객체
    :param limit: 페이지당 아이템 수
    :param offset: 시작 오프셋
    :return: SimplePage 객체
    """
    offset = (page - 1) * per_page

    # 요청한 limit + 1 개의 아이템을 가져옴
    items = query.limit(per_page + 1).offset(offset).all()

    # limit + 1개를 요청했는데 limit개만 있으면 다음 페이지가 없음
    has_next = len(items) > per_page

    # 실제로는 limit개만 반환
    if has_next:
        items = items[:per_page]

    return SimplePage(
        items=items,
        page=page,
        per_page=per_page,
        has_next=has_next
    )

