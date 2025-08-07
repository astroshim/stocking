from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.config.db import get_db
from app.config.get_current_user import get_current_user
from app.api.v1.schemas.stock_schema import (
    StockCreate, StockUpdate, StockResponse, StockWithPriceResponse,
    StockListResponse, StockSearchRequest, StockPriceCreate, StockPriceResponse
)
from app.utils.response_helper import create_response
from app.utils.simple_paging import SimplePage

router = APIRouter()


@router.get("/stocks", response_model=StockListResponse, summary="주식 목록 조회")
async def get_stocks(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    keyword: Optional[str] = Query(None, description="검색 키워드"),
    market: Optional[str] = Query(None, description="시장 구분"),
    sector: Optional[str] = Query(None, description="업종"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """
    주식 종목 목록을 조회합니다.
    - 검색 키워드, 시장, 업종으로 필터링 가능
    - 페이징 지원
    """
    # TODO: 실제 서비스 로직 구현
    page_result = SimplePage(
        items=[],
        page=page,
        per_page=size,
        has_next=False
    )
    
    response = StockListResponse.from_page_result(page_result)
    return create_response(response.model_dump(), message="주식 목록 조회 성공")


@router.get("/stocks/{stock_id}", response_model=StockWithPriceResponse, summary="주식 상세 조회")
async def get_stock(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """특정 주식 종목의 상세 정보를 조회합니다."""
    # TODO: 실제 서비스 로직 구현
    raise HTTPException(status_code=404, detail="Stock not found")


@router.post("/stocks", summary="주식 종목 등록")
async def create_stock(
    stock_data: StockCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """새로운 주식 종목을 등록합니다. (관리자 전용)"""
    # TODO: 권한 체크 및 실제 서비스 로직 구현
    return create_response(
        data=None,
        status_code=201,
        message="주식 종목이 성공적으로 등록되었습니다."
    )


@router.put("/stocks/{stock_id}", summary="주식 종목 수정")
async def update_stock(
    stock_id: str,
    stock_data: StockUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주식 종목 정보를 수정합니다. (관리자 전용)"""
    # TODO: 권한 체크 및 실제 서비스 로직 구현
    return create_response(
        data=None,
        message="주식 종목이 성공적으로 수정되었습니다."
    )


@router.delete("/stocks/{stock_id}", summary="주식 종목 삭제")
async def delete_stock(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주식 종목을 삭제합니다. (관리자 전용)"""
    # TODO: 권한 체크 및 실제 서비스 로직 구현
    return create_response(
        data=None,
        message="주식 종목이 성공적으로 삭제되었습니다."
    )


@router.post("/stocks/{stock_id}/prices", summary="주식 가격 등록")
async def create_stock_price(
    stock_id: str,
    price_data: StockPriceCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주식 가격 정보를 등록합니다."""
    # TODO: 실제 서비스 로직 구현
    return create_response(
        data=None,
        message="주식 가격이 성공적으로 등록되었습니다."
    )


@router.get("/stocks/{stock_id}/prices", response_model=List[StockPriceResponse], summary="주식 가격 이력 조회")
async def get_stock_prices(
    stock_id: str,
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="조회 개수"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주식의 가격 이력을 조회합니다."""
    # TODO: 실제 서비스 로직 구현
    return create_response([], message="주식 가격 이력 조회 성공")


@router.get("/stocks/{stock_id}/current-price", response_model=StockPriceResponse, summary="현재가 조회")
async def get_current_price(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """주식의 현재가를 조회합니다."""
    # TODO: 실제 서비스 로직 구현
    raise HTTPException(status_code=404, detail="Price not found")


@router.get("/markets", response_model=List[dict], summary="시장 목록 조회")
async def get_markets(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """사용 가능한 시장 목록을 조회합니다."""
    markets = [
        {"code": "KOSPI", "name": "코스피"},
        {"code": "KOSDAQ", "name": "코스닥"},
        {"code": "NASDAQ", "name": "나스닥"},
        {"code": "NYSE", "name": "뉴욕증권거래소"}
    ]
    return create_response(markets, message="시장 목록 조회 성공")


@router.get("/sectors", response_model=List[dict], summary="업종 목록 조회")
async def get_sectors(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user)
):
    """사용 가능한 업종 목록을 조회합니다."""
    sectors = [
        {"code": "TECH", "name": "기술주"},
        {"code": "FINANCE", "name": "금융주"},
        {"code": "MANUFACTURING", "name": "제조업"},
        {"code": "ENERGY", "name": "에너지"},
        {"code": "HEALTHCARE", "name": "헬스케어"}
    ]
    return create_response(sectors, message="업종 목록 조회 성공")