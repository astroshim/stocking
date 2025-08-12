from app.db.models.comment import Comment
from app.db.models.notice import Notice
from app.db.models.report import Report
from app.db.models.report_status_history import ReportStatusHistory
from app.db.models.role import Role, UserRole
from app.db.models.user import User

# 주식 거래 관련 모델들
from app.db.models.stock import Stock, StockPrice
from app.db.models.order import Order, OrderExecution
from app.db.models.portfolio import Portfolio
from app.db.models.virtual_balance import VirtualBalance, VirtualBalanceHistory
from app.db.models.transaction import Transaction, TradingStatistics, WatchList

# 모델 로딩 순서 문제 해결을 위해 아래와 같이 __all__ 변수를 정의
__all__ = [
    'User', 'Comment', 'Report', 'ReportStatusHistory', 'Notice', 'Role', 'UserRole',
    'Stock', 'StockPrice', 'Order', 'OrderExecution', 
    'Portfolio', 'VirtualBalance', 'VirtualBalanceHistory',
    'Transaction', 'TradingStatistics', 'WatchList'
]
