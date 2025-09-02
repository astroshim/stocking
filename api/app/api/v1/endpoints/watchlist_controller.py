from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.get_current_user import get_current_user
from app.config.di import get_portfolio_service
from app.services.portfolio_service import PortfolioService
from app.api.v1.schemas.portfolio_schema import (
    # 관심종목 관련
    WatchListCreate,
    WatchListUpdate,
    WatchListResponse,
    WatchListWithStockResponse,
    WatchListListResponse,
    # 디렉토리 관련
    WatchlistDirectoryCreate,
    WatchlistDirectoryUpdate,
    WatchlistDirectoryResponse,
    WatchlistDirectoryWithStatsResponse,
    WatchlistDirectoryListResponse,
    WatchlistDirectoryDetailResponse
)
from app.utils.response_helper import create_response
from app.utils.data_converters import DataConverters


router = APIRouter()


# ========== 관심종목 디렉토리 관련 API ==========

@router.post("/directories", response_model=WatchlistDirectoryResponse, summary="관심종목 디렉토리 생성")
async def create_watchlist_directory(
    directory_data: WatchlistDirectoryCreate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 디렉토리를 생성합니다."""
    try:
        directory = portfolio_service.create_watchlist_directory(
            user_id=current_user_id,
            name=directory_data.name,
            description=directory_data.description,
            color=directory_data.color
        )
        
        return create_response(
            data=DataConverters.convert_directory_to_dict(directory),
            status_code=201,
            message="관심종목 디렉토리가 성공적으로 생성되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 생성 실패: {str(e)}")


@router.get("/directories/default", response_model=WatchlistDirectoryResponse, summary="기본 관심종목 디렉토리 조회")
async def get_default_directory(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 기본 관심종목 디렉토리를 조회합니다."""
    try:
        default_directory = portfolio_service.get_default_directory(current_user_id)
        
        return create_response(
            data=default_directory,
            status_code=200,
            message="기본 디렉토리를 성공적으로 조회했습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"기본 디렉토리 조회 실패: {str(e)}")


@router.get("/directories", response_model=WatchlistDirectoryListResponse, summary="관심종목 디렉토리 목록")
async def get_watchlist_directories(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 관심종목 디렉토리 목록을 조회합니다."""
    try:
        directories_page = portfolio_service.get_watchlist_directories(
            user_id=current_user_id,
            page=page,
            size=size
        )
        
        paged_response = WatchlistDirectoryListResponse.from_page_result(directories_page)
        return create_response(
            data=paged_response.model_dump(),
            status_code=200,
            message="관심종목 디렉토리 목록을 성공적으로 조회했습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 목록 조회 실패: {str(e)}")


@router.get("/directories/{directory_id}", response_model=WatchlistDirectoryDetailResponse, summary="관심종목 디렉토리 상세")
async def get_watchlist_directory(
    directory_id: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 디렉토리의 상세 정보와 포함된 관심종목 목록을 조회합니다."""
    try:
        directory_detail = portfolio_service.get_watchlist_directory(
            user_id=current_user_id,
            directory_id=directory_id
        )
        
        if not directory_detail:
            raise HTTPException(status_code=404, detail="디렉토리를 찾을 수 없습니다.")
        
        return create_response(
            data=directory_detail,
            status_code=200,
            message="관심종목 디렉토리 상세 정보를 성공적으로 조회했습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 상세 조회 실패: {str(e)}")


@router.put("/directories/{directory_id}", response_model=WatchlistDirectoryResponse, summary="관심종목 디렉토리 수정")
async def update_watchlist_directory(
    directory_id: str,
    directory_data: WatchlistDirectoryUpdate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 디렉토리 정보를 수정합니다."""
    try:
        # 기본 디렉토리 이름 변경 방지
        default_directory_id = f"{current_user_id}-base"
        if directory_id == default_directory_id and directory_data.name and directory_data.name != "기본":
            raise HTTPException(status_code=400, detail="기본 디렉토리의 이름은 변경할 수 없습니다")
        
        directory = portfolio_service.update_watchlist_directory(
            user_id=current_user_id,
            directory_id=directory_id,
            name=directory_data.name,
            description=directory_data.description,
            color=directory_data.color
        )
        
        return create_response(
            data=DataConverters.convert_directory_to_dict(directory),
            status_code=200,
            message="관심종목 디렉토리가 성공적으로 수정되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 수정 실패: {str(e)}")


@router.delete("/directories/{directory_id}", summary="관심종목 디렉토리 삭제")
async def delete_watchlist_directory(
    directory_id: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 디렉토리를 삭제합니다. 디렉토리 내 관심종목은 기본 카테고리로 이동됩니다."""
    try:
        portfolio_service.delete_watchlist_directory(
            user_id=current_user_id,
            directory_id=directory_id
        )
        
        return create_response(
            data=None,
            status_code=200,
            message="관심종목 디렉토리가 성공적으로 삭제되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"디렉토리 삭제 실패: {str(e)}")


# ========== 관심종목 관련 API ==========

@router.post("/", summary="관심종목 추가")
async def add_to_watchlist(
    watchlist_data: WatchListCreate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목을 추가합니다."""
    try:
        watchlist = portfolio_service.add_to_watchlist(
            user_id=current_user_id,
            product_code=watchlist_data.product_code,
            directory_id=watchlist_data.directory_id,
            memo=watchlist_data.memo,
            target_price=watchlist_data.target_price
        )
        
        return create_response(
            data={'id': watchlist.id},
            status_code=201,
            message="관심종목이 성공적으로 추가되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심종목 추가 실패: {str(e)}")


@router.get("/", response_model=WatchListListResponse, summary="관심종목 목록")
async def get_watchlist(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    directory_id: Optional[str] = Query(None, description="디렉토리 ID 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터 (구버전 호환)"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 목록을 조회합니다."""
    try:
        watchlist_page = portfolio_service.get_watchlist(
            user_id=current_user_id,
            page=page,
            size=size,
            category=category
        )
        
        paged_response = WatchListListResponse.from_page_result(watchlist_page)
        return create_response(
            data=paged_response.model_dump(),
            status_code=200,
            message="관심종목 목록을 성공적으로 조회했습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심종목 목록 조회 실패: {str(e)}")


@router.put("/{watchlist_id}", summary="관심종목 수정")
async def update_watchlist(
    watchlist_id: str,
    watchlist_data: WatchListUpdate,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목 정보를 수정합니다."""
    try:
        portfolio_service.update_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id,
            category=watchlist_data.category,
            memo=watchlist_data.memo,
            target_price=watchlist_data.target_price
        )
        
        return create_response(
            data=None,
            status_code=200,
            message="관심종목이 성공적으로 수정되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심종목 수정 실패: {str(e)}")


@router.delete("/{watchlist_id}", summary="관심종목 삭제")
async def remove_from_watchlist(
    watchlist_id: str,
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목을 삭제합니다."""
    try:
        portfolio_service.remove_from_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id
        )
        
        return create_response(
            data=None,
            status_code=200,
            message="관심종목이 성공적으로 삭제되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심종목 삭제 실패: {str(e)}")


@router.put("/{watchlist_id}/order", summary="관심종목 순서 변경")
async def reorder_watchlist(
    watchlist_id: str,
    new_order: int = Query(..., description="새로운 순서"),
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """관심종목의 표시 순서를 변경합니다."""
    try:
        portfolio_service.reorder_watchlist(
            user_id=current_user_id,
            watchlist_id=watchlist_id,
            new_order=new_order
        )
        
        return create_response(
            data=None,
            status_code=200,
            message="관심종목 순서가 성공적으로 변경되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관심종목 순서 변경 실패: {str(e)}")


@router.get("/categories", response_model=list[dict], summary="관심종목 카테고리 목록")
async def get_watchlist_categories(
    current_user_id: str = Depends(get_current_user),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """사용자의 관심종목 카테고리 목록을 조회합니다 (구버전 호환)."""
    try:
        categories = portfolio_service.get_watchlist_categories(current_user_id)
        return create_response(
            data=categories,
            status_code=200,
            message="카테고리 목록 조회 성공"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테고리 목록 조회 실패: {str(e)}")
