from fastapi import APIRouter
from app.api.v1.endpoints import user_controller, \
    storage_controller, payment_controller, \
    order_controller, portfolio_controller, balance_controller, \
    trading_controller, kis_ws_controller, toss_requester_controller, \
    watchlist_controller, toss_ws_relayer_controller, toss_realtime_data_controller, toss_ws_controller

api_v1_router = APIRouter()

# 엔드포인트 등록
# api_v1_router.include_router(auth_controller.router, prefix="/auth", tags=["인증"])
api_v1_router.include_router(user_controller.router, prefix="/users", tags=["사용자 관리"])

# 주식 거래 관련 라우터
# api_v1_router.include_router(stock_controller.router, prefix="/trading", tags=["주식 관리"])
api_v1_router.include_router(order_controller.router, prefix="/trading", tags=["주문 관리"])
api_v1_router.include_router(portfolio_controller.router, prefix="/portfolio", tags=["포트폴리오 관리"])
api_v1_router.include_router(balance_controller.router, prefix="/balance", tags=["잔고 관리"])
api_v1_router.include_router(trading_controller.router, prefix="/trading", tags=["거래 분석"])

api_v1_router.include_router(watchlist_controller.router, prefix="/watchlist", tags=["관심종목 관리"])

api_v1_router.include_router(toss_requester_controller.router, prefix="/stocks", tags=["toss 프록시"])
api_v1_router.include_router(toss_ws_relayer_controller.router, prefix="/admin", tags=["Toss WebSocket Relayer를 API로 관리"])
api_v1_router.include_router(toss_realtime_data_controller.router, prefix="/trading", tags=["Toss Relayer Redis 실시간 데이터"])
api_v1_router.include_router(kis_ws_controller.router, prefix="/trading", tags=["한국투자증권(kis) 실시간 주식 데이터"])
api_v1_router.include_router(toss_ws_controller.router, prefix="/trading", tags=["Toss 실시간 주식 데이터"])

api_v1_router.include_router(payment_controller.router, prefix="/payments", tags=["결제 관리"])
api_v1_router.include_router(storage_controller.router, prefix="/storages", tags=["스토리지 관리"])

# api_v1_router.include_router(notice_controller.router, prefix="/notices", tags=["공지사항 관리"])
# api_v1_router.include_router(report_controller.router, prefix="/reports", tags=["신고 관리"])
# api_v1_router.include_router(comment_controller.router, prefix="/comments", tags=["댓글 관리"])
# api_v1_router.include_router(role_controller.router, prefix="/roles", tags=["역할 관리"])
# api_v1_router.include_router(routine_marketing_controller.router, prefix="/routine-marketing", tags=["루틴 마케팅 관리"])
