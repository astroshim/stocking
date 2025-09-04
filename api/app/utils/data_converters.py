from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

from app.db.models.watchlist import WatchList, WatchlistDirectory
from app.db.models.portfolio import Portfolio


class DataConverters:
    """데이터 변환을 위한 공통 유틸리티 클래스"""
    
    @staticmethod
    def convert_watchlist_to_dict(
        watchlist: WatchList, 
        include_product_details: bool = True,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """관심종목을 딕셔너리로 변환"""
        # 목표가 대비 변동률 계산
        target_achievement = None
        if watchlist.target_price and watchlist.target_price > 0 and current_price:
            target_achievement = float(
                (Decimal(str(current_price)) - Decimal(str(watchlist.target_price))) / 
                Decimal(str(watchlist.target_price)) * 100
            )
        
        # 스키마가 요구하는 모든 필드 포함
        watchlist_data = {
            'id': watchlist.id,
            'user_id': watchlist.user_id,
            'product_code': watchlist.product_code,
            'directory_id': watchlist.directory_id,
            'add_date': watchlist.add_date,
            'target_price': watchlist.target_price,
            'stop_loss_price': watchlist.stop_loss_price,
            'memo': watchlist.memo,
            'price_alert_enabled': watchlist.price_alert_enabled,
            'price_alert_upper': watchlist.price_alert_upper,
            'price_alert_lower': watchlist.price_alert_lower,
            'volume_alert_enabled': watchlist.volume_alert_enabled,
            'volume_alert_threshold': watchlist.volume_alert_threshold,
            'display_order': watchlist.display_order,
            'category': watchlist.category,
            'is_active': watchlist.is_active,
            'created_at': watchlist.created_at,
            'updated_at': watchlist.updated_at
        }
        
        # 추가 계산 필드들
        if target_achievement is not None:
            watchlist_data['target_achievement'] = target_achievement
        
        # 상품 상세 정보 포함 여부 (외부에서 별도로 조회해서 추가할 수 있음)
        if include_product_details and current_price is not None:
            watchlist_data['current_price'] = current_price
            watchlist_data['price_change'] = 0  # TODO: 전일대비 변동액
            watchlist_data['price_change_rate'] = 0  # TODO: 전일대비 변동률
        
        return watchlist_data
    
    @staticmethod
    def convert_portfolio_to_dict(portfolio: Portfolio) -> Dict[str, Any]:
        """포트폴리오를 딕셔너리로 변환"""
        # TODO: 실제 주식 가격 조회 로직 필요 (임시로 평균 매수가 사용)
        current_price = portfolio.average_price

        current_value = portfolio.current_quantity * current_price
        invested_amount = portfolio.current_quantity * portfolio.average_price
        unrealized_profit_loss = current_value - invested_amount
        unrealized_profit_loss_rate = (
            (unrealized_profit_loss / invested_amount * 100)
            if invested_amount > 0 else Decimal('0')
        )

        data = {
            'id': portfolio.id,
            'user_id': portfolio.user_id,
            'product_code': portfolio.product_code,
            'product_name': portfolio.product_name,
            'market': portfolio.market,
            'quantity': portfolio.current_quantity,
            'average_buy_price': portfolio.average_price,
            'total_buy_amount': portfolio.current_quantity * portfolio.average_price,
            'current_value': current_value,
            'unrealized_profit_loss': unrealized_profit_loss,
            'unrealized_profit_loss_rate': unrealized_profit_loss_rate,
            'first_buy_date': portfolio.first_buy_date,
            'last_buy_date': portfolio.last_buy_date,
            'last_sell_date': portfolio.last_sell_date,
            'last_updated_at': portfolio.last_updated_at,
            'is_active': portfolio.is_active,
            'notes': portfolio.notes,
            'created_at': portfolio.created_at,
            'updated_at': portfolio.updated_at,
            'current_price': current_price,
        }

        # 주문 목록 변환 (간략 정보)
        try:
            orders = []
            if hasattr(portfolio, 'orders') and portfolio.orders:
                for o in portfolio.orders:
                    orders.append({
                        'id': o.id,
                        'order_type': o.order_type,
                        'order_method': o.order_method,
                        'order_status': o.order_status,
                        'quantity': o.quantity,
                        'order_price': o.order_price,
                        'currency': getattr(o, 'currency', 'KRW'),
                        'exchange_rate': getattr(o, 'exchange_rate', None),
                        'created_at': o.created_at,
                    })
            data['orders'] = orders
        except Exception:
            data['orders'] = []

        return data
    
    @staticmethod
    def convert_directory_to_dict(
        directory: WatchlistDirectory, 
        include_stats: bool = False,
        watchlist_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """관심종목 디렉토리를 딕셔너리로 변환"""
        directory_data = {
            'id': directory.id,
            'user_id': directory.user_id,
            'name': directory.name,
            'description': directory.description,
            'display_order': directory.display_order,
            'color': directory.color,
            'is_active': directory.is_active,
            'created_at': directory.created_at.isoformat(),
            'updated_at': directory.updated_at.isoformat()
        }
        
        # 통계 정보 포함 여부
        if include_stats and watchlist_count is not None:
            directory_data['watchlist_count'] = watchlist_count
        
        return directory_data
