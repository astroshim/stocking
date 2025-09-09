from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date

from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.transaction_repository import TransactionRepository
from app.db.models.portfolio import Portfolio
from app.utils.simple_paging import SimplePage
from app.utils.data_converters import DataConverters
from app.services.toss_proxy_service import TossProxyService


class PortfolioService:
    """포트폴리오 서비스"""

    def __init__(self, db: Session, toss_proxy_service: Optional[TossProxyService] = None):
        self.db = db
        self.portfolio_repo = PortfolioRepository(db)
        self.transaction_repo = TransactionRepository(db)
        self.toss_proxy_service = toss_proxy_service
        # watchlist 관련 로직은 WatchListService로 이동

    def get_user_portfolio(
        self, 
        user_id: str,
        page: int = 1,
        size: int = 20,
        only_active: bool = True,
        include_orders: bool = False
    ) -> SimplePage:
        """사용자 포트폴리오 조회"""
        portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active, include_orders)
        
        # 페이징 처리
        offset = (page - 1) * size
        total_items = len(portfolios)
        paged_portfolios = portfolios[offset:offset + size]
        
        # 포트폴리오 데이터 변환
        portfolio_data = []
        for portfolio in paged_portfolios:
            item = DataConverters.convert_portfolio_to_dict(portfolio, include_orders)
            # 실현 손익률(%) = 누적 실현손익(KRW) / 누적 실현원가(KRW) * 100
            try:
                krw_realized = getattr(portfolio, 'krw_realized_profit_loss', None)
                if krw_realized is not None:
                    realized_cost = self.transaction_repo.get_realized_cost_krw_by_stock(portfolio.user_id, portfolio.product_code)
                    if realized_cost and realized_cost > 0:
                        item['realized_profit_loss_rate'] = float((Decimal(str(krw_realized)) / realized_cost) * Decimal('100'))
                    else:
                        item['realized_profit_loss_rate'] = None
                else:
                    item['realized_profit_loss_rate'] = None
            except Exception:
                item['realized_profit_loss_rate'] = None
            portfolio_data.append(item)
        
        return SimplePage(
            items=portfolio_data,
            page=page,
            per_page=size,
            has_next=offset + size < total_items
        )

    def get_portfolio_summary(self, user_id: str) -> Dict[str, Any]:
        """포트폴리오 요약 정보 조회"""
        return self.portfolio_repo.get_portfolio_summary(user_id)

    def get_portfolio_analysis(self, user_id: str) -> Dict[str, Any]:
        exchange_rate = self.toss_proxy_service.get_exchange_rate('USD')
        print(f"-----------> exchange_rate: {exchange_rate}")

        """포트폴리오 분석 정보 조회 (환율 반영 라이브 지표 포함)"""
        sector_allocation = self.portfolio_repo.get_sector_allocation(user_id)
        top_holdings = self.portfolio_repo.get_top_holdings(user_id)
        
        # 성과 지표 계산
        summary = self.portfolio_repo.get_portfolio_summary(user_id)
        performance_metrics = {
            'total_return': float(summary['total_profit_loss']),
            'total_return_rate': float(summary['total_profit_loss_rate']),
            'total_invested': float(summary['total_invested_amount']),
            'current_value': float(summary['total_current_value'])
        }
        
        # 리스크 지표 (간단한 계산)
        total_current_value_float = float(summary['total_current_value']) if summary['total_current_value'] is not None else 0.0
        max_holding_value = max([holding.get('current_value', 0.0) for holding in top_holdings], default=0.0)
        risk_metrics = {
            'diversification_score': len(sector_allocation),  # 섹터 다양성
            'concentration_risk': (
                (max_holding_value / total_current_value_float * 100.0)
                if total_current_value_float > 0.0 else 0.0
            )
        }
        
        # # Toss 환율 반영: 섹터별 라이브 지표 보강
        # try:
        #     portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active=True, include_orders=False)
        #     currency_to_rate: Dict[str, Decimal] = {}
        #     if self.toss_proxy_service:
        #         unique_currencies = set([str(getattr(p, 'base_currency', 'KRW') or 'KRW') for p in portfolios])
        #         for cur in unique_currencies:
        #             try:
        #                 currency_to_rate[cur] = self.toss_proxy_service.get_exchange_rate(cur, 'KRW')
        #             except Exception:
        #                 currency_to_rate[cur] = Decimal('1.0') if cur == 'KRW' else Decimal('0')
        #     else:
        #         currency_to_rate['KRW'] = Decimal('1.0')

        #     sector_live: Dict[str, Dict[str, Any]] = {}
        #     total_current_value_live = Decimal('0')
        #     total_unrealized_live = Decimal('0')

        #     for p in portfolios:
        #         code = str(getattr(p, 'industry_code', None) or '기타')
        #         display = str(getattr(p, 'industry_display', None) or '기타')
        #         base_currency = str(getattr(p, 'base_currency', 'KRW') or 'KRW')
        #         rate = currency_to_rate.get(base_currency, Decimal('1.0')) or Decimal('1.0')

        #         quantity = Decimal(str(p.current_quantity or 0))
        #         avg_price_local = Decimal(str(p.average_price or 0))

        #         current_value_live = quantity * avg_price_local * rate

        #         if getattr(p, 'krw_total_buy_amount', None):
        #             invested_krw = Decimal(str(p.krw_total_buy_amount))
        #         elif getattr(p, 'krw_average_price', None) is not None:
        #             invested_krw = quantity * Decimal(str(p.krw_average_price))
        #         else:
        #             invested_krw = quantity * avg_price_local * rate

        #         unrealized_live = current_value_live - invested_krw

        #         if code not in sector_live:
        #             sector_live[code] = {
        #                 'industry_code': code,
        #                 'industry_display': display,
        #                 'value_live': Decimal('0'),
        #                 'invested_live': Decimal('0'),
        #                 'unrealized_live': Decimal('0'),
        #                 'count': 0
        #             }
        #         sector_live[code]['value_live'] += current_value_live
        #         sector_live[code]['invested_live'] += invested_krw
        #         sector_live[code]['unrealized_live'] += unrealized_live
        #         sector_live[code]['count'] += 1

        #         total_current_value_live += current_value_live
        #         total_unrealized_live += unrealized_live

        #     enriched = []
        #     for code, s in sector_live.items():
        #         percentage_live = float((s['value_live'] / total_current_value_live * 100) if total_current_value_live > 0 else 0)
        #         profit_loss_rate_live = float((s['unrealized_live'] / s['invested_live'] * 100) if s['invested_live'] > 0 else 0)
        #         profit_loss_pct_of_total_live = float((s['unrealized_live'] / total_unrealized_live * 100) if total_unrealized_live != 0 else 0)
        #         enriched.append({
        #             'industry_code': s['industry_code'],
        #             'industry_display': s['industry_display'],
        #             'value_live': float(s['value_live']),
        #             'count': s['count'],
        #             'percentage_live': percentage_live,
        #             'profit_loss_live': float(s['unrealized_live']),
        #             'profit_loss_rate_live': profit_loss_rate_live,
        #             'profit_loss_percentage_of_total_live': profit_loss_pct_of_total_live
        #         })

        #     sector_allocation_map = { (d.get('industry_code') or d.get('sector') or '기타'): d for d in sector_allocation }
        #     for e in enriched:
        #         key = e['industry_code']
        #         base = sector_allocation_map.get(key, {'industry_code': key, 'industry_display': e['industry_display']})
        #         base.update({
        #             'value_live': e['value_live'],
        #             'percentage_live': e['percentage_live'],
        #             'profit_loss_live': e['profit_loss_live'],
        #             'profit_loss_rate_live': e['profit_loss_rate_live'],
        #             'profit_loss_percentage_of_total_live': e['profit_loss_percentage_of_total_live']
        #         })
        #         sector_allocation_map[key] = base
        #     sector_allocation = list(sector_allocation_map.values())
        # except Exception:
        #     pass

        return {
            'sector_allocation': sector_allocation,
            'top_holdings': top_holdings,
            'performance_metrics': performance_metrics,
            'risk_metrics': risk_metrics
        }

    def get_portfolio_by_stock(self, user_id: str, product_code: str) -> Optional[Dict[str, Any]]:
        """특정 종목 포트폴리오 조회 (product_code 기반)"""
        portfolio = self.portfolio_repo.get_by_user_and_stock(user_id, product_code)
        
        if not portfolio:
            return None
        
        item = DataConverters.convert_portfolio_to_dict(portfolio, include_orders=False)
        try:
            krw_realized = getattr(portfolio, 'krw_realized_profit_loss', None)
            if krw_realized is not None:
                realized_cost = self.transaction_repo.get_realized_cost_krw_by_stock(portfolio.user_id, product_code)
                if realized_cost and realized_cost > 0:
                    item['realized_profit_loss_rate'] = float((Decimal(str(krw_realized)) / realized_cost) * Decimal('100'))
                else:
                    item['realized_profit_loss_rate'] = None
            else:
                item['realized_profit_loss_rate'] = None
        except Exception:
            item['realized_profit_loss_rate'] = None
        return item
