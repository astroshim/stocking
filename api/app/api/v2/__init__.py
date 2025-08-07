from fastapi import APIRouter

from app.api.v2.endpoints import hi

api_v2_router = APIRouter()

# 엔드포인트 등록
api_v2_router.include_router(hi.router, prefix="/hi", tags=["Hi"])
