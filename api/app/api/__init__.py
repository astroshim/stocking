from fastapi import APIRouter
from app.api.v1 import api_v1_router
from app.api.v2 import api_v2_router

api_router = APIRouter()

api_router.include_router(api_v1_router, prefix="/v1")
api_router.include_router(api_v2_router, prefix="/v2")
