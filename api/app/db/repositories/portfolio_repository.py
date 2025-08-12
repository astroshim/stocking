from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from decimal import Decimal

from app.db.repositories.base_repository import BaseRepository
from app.db.models.portfolio import Portfolio


class PortfolioRepository(BaseRepository):
    """포트폴리오 레포지토리"""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_user_id(self, user_id: str, only_active: bool = True) -> List[Portfolio]:
        """사용자의 포트폴리오 목록 조회"""
        query = self.session.query(Portfolio).filter(Portfolio.user_id == user_id)
        
        if only_active:
            query = query.filter(Portfolio.current_quantity > 0)
        
        return query.order_by(desc(Portfolio.updated_at)).all()

    def get_by_user_and_stock(self, user_id: str, stock_id: str) -> Optional[Portfolio]:
        """사용자의 특정 종목 포트폴리오 조회"""
        return self.session.query(Portfolio).filter(
            and_(
                Portfolio.user_id == user_id,
                Portfolio.stock_id == stock_id
            )
        ).first()

    def create_portfolio(
        self,
        user_id: str,
        stock_id: str,
        quantity: int,
        average_price: Decimal
    ) -> Portfolio:
        """새 포트폴리오 생성"""
        from datetime import datetime
        
        now = datetime.now()
        portfolio = Portfolio(
            user_id=user_id,
            stock_id=stock_id,
            current_quantity=quantity,
            average_price=average_price,
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
        price: Decimal
    ) -> Portfolio:
        """매수 시 포트폴리오 업데이트"""
        from datetime import datetime
        
        # 평균 단가 계산 (총량/총원가 없이 이동평균)
        new_total_amount = (portfolio.average_price * portfolio.current_quantity) + (price * quantity)
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
        
        # 실현 손익 계산 (매도 가격 - 기존 평단) * 수량
        realized_profit_loss = (price - portfolio.average_price) * quantity
        portfolio.current_quantity -= quantity
        portfolio.realized_profit_loss += realized_profit_loss
        
        # 현재 수량이 0이 되면 평균 단가 초기화
        if portfolio.current_quantity == 0:
            portfolio.average_price = Decimal('0')
        
        from datetime import datetime
        portfolio.last_sell_date = datetime.now()
        portfolio.last_updated_at = datetime.now()
        
        return portfolio

    def get_portfolio_summary(self, user_id: str) -> dict:
        """포트폴리오 요약 정보 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True)
        
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
        portfolios = self.get_by_user_id(user_id, only_active=True)
        
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
        portfolios = self.get_by_user_id(user_id, only_active=True)
        
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
                'stock_code': portfolio.stock_id,  # stock_id 사용
                'stock_name': f"주식 {portfolio.stock_id}",  # 임시 이름
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
