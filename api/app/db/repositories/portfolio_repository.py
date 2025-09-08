from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc
from decimal import Decimal

from app.db.repositories.base_repository import BaseRepository
from app.db.models.portfolio import Portfolio


class PortfolioRepository(BaseRepository):
    """포트폴리오 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_user_id(self, user_id: str, only_active: bool = True, include_orders: bool = True) -> List[Portfolio]:
        """사용자의 포트폴리오 목록 조회"""
        query = self.session.query(Portfolio)
        
        # N+1 쿼리 방지를 위해 orders를 eager loading (필요한 경우에만)
        if include_orders:
            query = query.options(joinedload(Portfolio.orders))
            
        query = query.filter(Portfolio.user_id == user_id)
        
        if only_active:
            query = query.filter(Portfolio.current_quantity > 0)
        
        return query.order_by(desc(Portfolio.updated_at)).all()

    def get_by_user_and_stock(self, user_id: str, stock_id: str) -> Optional[Portfolio]:
        """사용자의 특정 종목 포트폴리오 조회 (N+1 쿼리 방지를 위해 orders를 eager loading)"""
        return self.session.query(Portfolio).options(joinedload(Portfolio.orders)).filter(
            and_(
                Portfolio.user_id == user_id,
                Portfolio.product_code == stock_id
            )
        ).first()

    def create_portfolio(
        self,
        user_id: str,
        product_code: str,
        quantity: int,
        average_price: Decimal,
        product_name: Optional[str] = None,
        market: Optional[str] = None,
        product_type: Optional[object] = None,
        symbol: Optional[str] = None,
        base_currency: Optional[str] = None,
        average_exchange_rate: Optional[Decimal] = None,
        krw_average_price: Optional[Decimal] = None,
    ) -> Portfolio:
        """새 포트폴리오 생성 (product_code 기반)"""
        from datetime import datetime
        from app.db.models.portfolio import ProductType as _PT
        
        now = datetime.now()
        
        # 초기 총 구매금액 계산
        total_buy_amount = average_price * quantity
        krw_total_buy_amount = krw_average_price * quantity if krw_average_price else None
        
        portfolio = Portfolio(
            user_id=user_id,
            product_code=product_code,
            product_name=product_name or product_code,
            market=market or "UNKNOWN",
            product_type=product_type or _PT.STOCK,
            symbol=symbol,
            base_currency=base_currency,
            current_quantity=quantity,
            average_price=average_price,
            total_buy_amount=total_buy_amount,
            krw_total_buy_amount=krw_total_buy_amount,
            average_exchange_rate=average_exchange_rate,
            krw_average_price=krw_average_price,
            first_buy_date=now,
            last_buy_date=now,
            last_updated_at=now
        )
        
        self.session.add(portfolio)
        self.session.flush()
        return portfolio

    def update_portfolio_buy(
        self,
        portfolio: Portfolio,
        quantity: int,
        price: Decimal,
        krw_price: Optional[Decimal] = None
    ) -> Portfolio:
        """매수 시 포트폴리오 업데이트"""
        from datetime import datetime
        
        # 이번 매수 금액
        buy_amount = price * quantity
        krw_buy_amount = krw_price * quantity if krw_price else buy_amount
        
        # 총 구매금액 업데이트
        portfolio.total_buy_amount = (portfolio.total_buy_amount or Decimal('0')) + buy_amount
        if krw_price:
            portfolio.krw_total_buy_amount = (portfolio.krw_total_buy_amount or Decimal('0')) + krw_buy_amount
        
        # 평균 단가 계산 (기존 로직 유지)
        new_total_amount = (portfolio.average_price * portfolio.current_quantity) + buy_amount
        new_total_quantity = portfolio.current_quantity + quantity
        portfolio.average_price = (new_total_amount / new_total_quantity) if new_total_quantity > 0 else Decimal('0')
        portfolio.current_quantity = new_total_quantity
        portfolio.last_buy_date = datetime.now()
        portfolio.last_updated_at = datetime.now()
        
        return portfolio

    def update_portfolio_sell(
        self,
        portfolio: Portfolio,
        quantity: int,
        price: Decimal
    ) -> Portfolio:
        """매도 시 포트폴리오 업데이트"""
        if portfolio.current_quantity < quantity:
            raise ValueError("보유 수량이 부족합니다")
        
        # 수량 차감 (실현 손익은 트랜잭션에서 관리)
        portfolio.current_quantity -= quantity
        
        # 현재 수량이 0이 되면 평균 단가 초기화
        if portfolio.current_quantity == 0:
            portfolio.average_price = Decimal('0')
        
        from datetime import datetime
        portfolio.last_sell_date = datetime.now()
        portfolio.last_updated_at = datetime.now()
        
        return portfolio

    def get_portfolio_summary(self, user_id: str) -> dict:
        """포트폴리오 요약 정보 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        total_stocks = len(portfolios)
        total_invested_amount = Decimal('0')
        total_current_value = Decimal('0')
        
        for portfolio in portfolios:
            total_invested_amount += portfolio.current_quantity * portfolio.average_price
            
            # TODO: 실제 주식 가격 조회 로직 필요
            # 임시로 평균 매수가를 현재가로 사용
            current_price = portfolio.average_price  # 임시 값
            current_value = portfolio.current_quantity * current_price
            total_current_value += current_value
        
        total_profit_loss = total_current_value - total_invested_amount
        total_profit_loss_rate = (
            (total_profit_loss / total_invested_amount * 100) 
            if total_invested_amount > 0 else Decimal('0')
        )
        
        return {
            'total_stocks': total_stocks,
            'total_invested_amount': total_invested_amount,
            'total_current_value': total_current_value,
            'total_profit_loss': total_profit_loss,
            'total_profit_loss_rate': total_profit_loss_rate
        }

    def get_sector_allocation(self, user_id: str) -> List[dict]:
        """섹터별 배분 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        sector_data = {}
        total_value = Decimal('0')
        
        for portfolio in portfolios:
            # TODO: 실제 주식 가격 및 섹터 정보 조회 필요
            current_price = portfolio.average_price  # 임시 값
            current_value = portfolio.current_quantity * current_price
            sector = "기타"  # 임시 값 (stock 정보 없음)
            
            if sector not in sector_data:
                sector_data[sector] = {
                    'sector': sector,
                    'value': Decimal('0'),
                    'count': 0
                }
            
            sector_data[sector]['value'] += current_value
            sector_data[sector]['count'] += 1
            total_value += current_value
        
        # 비율 계산
        for sector_info in sector_data.values():
            sector_info['percentage'] = (
                float(sector_info['value'] / total_value * 100) 
                if total_value > 0 else 0
            )
        
        return list(sector_data.values())

    def get_top_holdings(self, user_id: str, limit: int = 5) -> List[dict]:
        """상위 보유 종목 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        holdings = []
        for portfolio in portfolios:
            # TODO: 실제 주식 정보 조회 필요
            current_price = portfolio.average_price  # 임시 값
            current_value = portfolio.current_quantity * current_price
            profit_loss = current_value - (portfolio.current_quantity * portfolio.average_price)
            profit_loss_rate = (
                (profit_loss / (portfolio.current_quantity * portfolio.average_price) * 100)
                if portfolio.average_price > 0 else 0
            )
            
            holdings.append({
                'product_code': portfolio.product_code,
                'product_name': portfolio.product_name,
                'quantity': portfolio.current_quantity,
                'current_value': current_value,
                'profit_loss': profit_loss,
                'profit_loss_rate': profit_loss_rate
            })
        
        # 현재 가치 기준 내림차순 정렬
        holdings.sort(key=lambda x: x['current_value'], reverse=True)
        
        return holdings[:limit]

    def delete_empty_portfolio(self, portfolio: Portfolio):
        """빈 포트폴리오 삭제 (수량이 0인 경우)"""
        if portfolio.current_quantity == 0:
            self.session.delete(portfolio)
