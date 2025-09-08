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

    def get_by_user_id(self, user_id: str, only_active: bool = True, include_orders: bool = False) -> List[Portfolio]:
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
        industry_code: Optional[str] = None,
        industry_display: Optional[str] = None,
    ) -> Portfolio:
        """새 포트폴리오 생성 (product_code 기반)"""
        from datetime import datetime
        from app.db.models.portfolio import ProductType as _PT
        
        now = datetime.now()
        
        # 초기 총 구매금액 계산
        total_buy_amount = average_price * quantity
        # krw_average_price가 주어지면 해당 단가로 총 원화 매수금액 계산
        krw_total_buy_amount = (krw_average_price * quantity) if krw_average_price else None
        
        portfolio = Portfolio(
            user_id=user_id,
            product_code=product_code,
            product_name=product_name or product_code,
            market=market or "UNKNOWN",
            industry_code=industry_code,
            industry_display=industry_display,
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
        
        # 총 구매금액 업데이트 (현지통화, KRW)
        portfolio.total_buy_amount = (portfolio.total_buy_amount or Decimal('0')) + buy_amount
        if krw_price is not None:
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
        
        # 매도에 따른 총 매수원가 감소: 평균단가 * 매도수량
        # total_buy_amount는 보유 원가 총액을 의미하도록 유지
        try:
            decrease_cost = (portfolio.average_price or Decimal('0')) * quantity
            portfolio.total_buy_amount = max(Decimal('0'), (portfolio.total_buy_amount or Decimal('0')) - decrease_cost)
            if portfolio.krw_average_price is not None:
                decrease_cost_krw = (portfolio.krw_average_price or Decimal('0')) * quantity
                current_krw_total = portfolio.krw_total_buy_amount or Decimal('0')
                # None일 수 있으니 안전하게 처리
                portfolio.krw_total_buy_amount = max(Decimal('0'), current_krw_total - decrease_cost_krw)
        except Exception:
            # 감소 계산 실패 시 원가 필드는 변경하지 않음
            pass

        # 현재 수량이 0이 되면 평균 단가 초기화
        if portfolio.current_quantity == 0:
            portfolio.average_price = Decimal('0')
            # KRW 평균단가도 초기화
            if hasattr(portfolio, 'krw_average_price'):
                portfolio.krw_average_price = None
        
        from datetime import datetime
        portfolio.last_sell_date = datetime.now()
        portfolio.last_updated_at = datetime.now()
        
        return portfolio

    def get_portfolio_summary(self, user_id: str) -> dict:
        """포트폴리오 요약 정보 조회 (현지통화/원화 동시 집계, 손익은 KRW 기준)"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        total_stocks = len(portfolios)
        total_invested_amount = Decimal('0')  # 현지통화 합계
        total_invested_amount_krw = Decimal('0')  # KRW 합계
        total_current_value = Decimal('0')  # 현지통화 합계 (임시)
        total_current_value_krw = Decimal('0')  # KRW 합계 (임시)
        total_profit_loss_krw = Decimal('0')  # KRW 기준 손익 (누적 실현손익 합)

        for portfolio in portfolios:
            # 투자금액: 평균매수가 * 수량
            total_invested_amount += portfolio.current_quantity * portfolio.average_price
            if getattr(portfolio, 'krw_average_price', None) is not None:
                total_invested_amount_krw += (portfolio.current_quantity * portfolio.krw_average_price)

            # 현재가치(임시): 평균가를 현재가로 사용 중
            current_price = portfolio.average_price
            current_value = portfolio.current_quantity * current_price
            total_current_value += current_value
            if getattr(portfolio, 'krw_average_price', None) is not None:
                total_current_value_krw += (portfolio.current_quantity * portfolio.krw_average_price)

            # 누적 실현 손익 (KRW)
            total_profit_loss_krw += (portfolio.krw_realized_profit_loss or Decimal('0'))
        
        # 손익률 (KRW 기준): 실현손익 / (KRW 투자금액) * 100
        total_profit_loss_rate = (
            (total_profit_loss_krw / total_invested_amount_krw * 100)
            if total_invested_amount_krw > 0 else Decimal('0')
        )
        
        return {
            'total_stocks': total_stocks,
            'total_invested_amount': total_invested_amount,
            'total_invested_amount_krw': total_invested_amount_krw if total_invested_amount_krw > 0 else None,
            'total_current_value': total_current_value,
            'total_current_value_krw': total_current_value_krw if total_current_value_krw > 0 else None,
            'total_profit_loss': total_profit_loss_krw,
            'total_profit_loss_rate': total_profit_loss_rate
        }

    def get_sector_allocation(self, user_id: str) -> List[dict]:
        """섹터별 배분 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        sector_data = {}
        total_value = Decimal('0')
        
        for portfolio in portfolios:
            # 현재가치 (임시: 평균가 사용)
            current_price = portfolio.average_price
            current_value = portfolio.current_quantity * current_price

            # industry_code 기준 그룹핑, null은 "기타"
            code = getattr(portfolio, 'industry_code', None) or '기타'
            display = getattr(portfolio, 'industry_display', None) or '기타'

            if code not in sector_data:
                sector_data[code] = {
                    'industry_code': code,
                    'industry_display': display,
                    'value': Decimal('0'),
                    'count': 0,
                    'invested_krw': Decimal('0'),
                    'realized_krw': Decimal('0')
                }

            sector_data[code]['value'] += current_value
            sector_data[code]['count'] += 1
            # 최신 display가 있는 경우 보강
            if display and sector_data[code].get('industry_display') in (None, '기타'):
                sector_data[code]['industry_display'] = display

            # 투자 원가(KRW) 및 누적 실현손익(KRW) 합산
            if getattr(portfolio, 'krw_average_price', None) is not None:
                sector_data[code]['invested_krw'] += (portfolio.current_quantity * portfolio.krw_average_price)
            sector_data[code]['realized_krw'] += (portfolio.krw_realized_profit_loss or Decimal('0'))

            total_value += current_value
        
        # 비율 계산
        # 전체 실현손익(KRW) 합계 (0 분모 방지)
        total_realized_krw = sum((info.get('realized_krw', Decimal('0')) for info in sector_data.values()), Decimal('0'))

        for sector_info in sector_data.values():
            sector_info['percentage'] = (
                float(sector_info['value'] / total_value * 100)
                if total_value > 0 else 0
            )
            # 숫자 직렬화 안정화: Decimal -> float
            sector_info['value'] = float(sector_info['value'])
            # 섹터별 손익(실현) 및 손익률(KRW 기준)
            invested_krw = sector_info.pop('invested_krw', Decimal('0'))
            realized_krw = sector_info.pop('realized_krw', Decimal('0'))
            sector_info['profit_loss'] = float(realized_krw)
            sector_info['profit_loss_rate'] = float((realized_krw / invested_krw * 100) if invested_krw > 0 else 0)
            # 전체 실현손익 대비 비중 (%)
            sector_info['profit_loss_percentage_of_total'] = float((realized_krw / total_realized_krw * 100) if total_realized_krw != 0 else 0)
        
        return list(sector_data.values())

    def get_top_holdings(self, user_id: str, limit: int = 5) -> List[dict]:
        """상위 보유 종목 조회"""
        portfolios = self.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        holdings = []
        for portfolio in portfolios:
            # TODO: 실제 주식 정보 조회 필요
            current_price = portfolio.average_price  # 임시 값
            current_value = portfolio.current_quantity * current_price

            # 손익(KRW 기준): 누적 실현손익 사용 (실시간 미연동 환경 대응)
            profit_loss_krw = (portfolio.krw_realized_profit_loss or Decimal('0'))
            # 손익률 분모: 현재 보유 원가(KRW). krw_total_buy_amount가 있으면 사용, 없으면 krw_average_price 기반 계산
            invested_krw = portfolio.krw_total_buy_amount
            if not invested_krw and getattr(portfolio, 'krw_average_price', None) is not None:
                invested_krw = portfolio.current_quantity * portfolio.krw_average_price
            profit_loss_rate = (float((profit_loss_krw / invested_krw) * 100) if invested_krw and invested_krw > 0 else 0.0)
            
            holdings.append({
                'product_code': portfolio.product_code,
                'product_name': portfolio.product_name,
                'industry_code': getattr(portfolio, 'industry_code', None),
                'industry_display': getattr(portfolio, 'industry_display', None),
                'quantity': float(portfolio.current_quantity),
                'current_value': float(current_value),
                'profit_loss': float(profit_loss_krw),
                'profit_loss_rate': float(profit_loss_rate)
            })
        
        # 현재 가치 기준 내림차순 정렬
        holdings.sort(key=lambda x: x['current_value'], reverse=True)
        
        return holdings[:limit]

    def delete_empty_portfolio(self, portfolio: Portfolio):
        """빈 포트폴리오 삭제 (수량이 0인 경우)"""
        if portfolio.current_quantity == 0:
            self.session.delete(portfolio)
