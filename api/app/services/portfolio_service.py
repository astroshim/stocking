from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, date
import logging

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
    
    def _cache_exchange_rates(self, portfolios: List[Portfolio]) -> Dict[str, Decimal]:
        """포트폴리오 목록에서 필요한 환율 정보를 캐싱합니다."""
        exchange_rates = {}
        for portfolio in portfolios:
            if portfolio.base_currency and portfolio.base_currency != 'KRW':
                if portfolio.base_currency not in exchange_rates:
                    if self.toss_proxy_service:
                        try:
                            exchange_rates[portfolio.base_currency] = self.toss_proxy_service.get_exchange_rate(portfolio.base_currency)
                        except Exception:
                            if portfolio.average_exchange_rate:
                                exchange_rates[portfolio.base_currency] = portfolio.average_exchange_rate
                            else:
                                exchange_rates[portfolio.base_currency] = Decimal('1')
                    elif portfolio.average_exchange_rate:
                        exchange_rates[portfolio.base_currency] = portfolio.average_exchange_rate
                    else:
                        exchange_rates[portfolio.base_currency] = Decimal('1')
        return exchange_rates
    
    def _cache_stock_prices(self, portfolios: List[Portfolio]) -> Dict[str, Optional[Decimal]]:
        """포트폴리오 목록에서 필요한 주가 정보를 캐싱합니다."""
        if not self.toss_proxy_service:
            return {p.product_code: None for p in portfolios}
        
        # 중복 제거된 종목 코드 리스트
        unique_codes = list(set(p.product_code for p in portfolios if p.product_code))
        
        if not unique_codes:
            return {}
        
        try:
            # 배치 API 호출로 모든 종목 가격을 한 번에 조회
            price_data_map = self.toss_proxy_service.get_stock_prices_batch(unique_codes)
            
            # current_price만 추출
            stock_prices = {}
            for code, price_data in price_data_map.items():
                if price_data and 'current_price' in price_data:
                    stock_prices[code] = price_data['current_price']
                else:
                    stock_prices[code] = None
            
            return stock_prices
            
        except Exception as e:
            logging.error(f"Error caching stock prices: {str(e)}")
            return {code: None for code in unique_codes}
    
    def _calculate_krw_amount(self, amount: Decimal, currency: Optional[str], exchange_rates: Dict[str, Decimal]) -> Decimal:
        """외화 금액을 KRW로 환산합니다."""
        if not currency or currency == 'KRW':
            return amount
        exchange_rate = exchange_rates.get(currency, Decimal('1'))
        return amount * exchange_rate
    
    def _calculate_portfolio_cost_krw(self, portfolio: Portfolio, exchange_rates: Dict[str, Decimal]) -> Decimal:
        """포트폴리오의 원가를 KRW로 계산합니다."""
        if portfolio.krw_average_price:
            return portfolio.krw_average_price * portfolio.current_quantity
        elif portfolio.average_price:
            cost = portfolio.average_price * portfolio.current_quantity
            return self._calculate_krw_amount(cost, portfolio.base_currency, exchange_rates)
        return Decimal('0')
    
    def _calculate_portfolio_value_krw(self, portfolio: Portfolio, stock_prices: Dict[str, Optional[Decimal]], exchange_rates: Dict[str, Decimal]) -> Decimal:
        """포트폴리오의 현재 가치를 KRW로 계산합니다."""
        current_price = stock_prices.get(portfolio.product_code)
        if current_price is None:
            current_price = portfolio.average_price or Decimal('0')
        
        value = current_price * portfolio.current_quantity
        return self._calculate_krw_amount(value, portfolio.base_currency, exchange_rates)

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
    
    def get_portfolio_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        포트폴리오 대시보드 정보를 조회합니다.
        - 원금, 평가금액, 총수익
        - 일간 손익금/손익률
        """
        portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        if not portfolios:
            return {
                'total_invested_amount': 0,
                'total_current_value': 0,
                'total_profit_loss': 0,
                'total_profit_loss_rate': 0,
                'daily_profit_loss': 0,
                'daily_profit_loss_rate': 0
            }
        
        # 환율 및 주가 정보 캐싱
        exchange_rates = self._cache_exchange_rates(portfolios)
        
        total_invested_krw = Decimal('0')  # 원금 (KRW)
        total_current_value_krw = Decimal('0')  # 현재 평가금액 (KRW)
        daily_profit_loss_krw = Decimal('0')  # 일간 손익금 (KRW)
        
        for portfolio in portfolios:
            if portfolio.current_quantity <= 0:
                continue
            
            # 원금 계산 (KRW 기준)
            position_cost_krw = self._calculate_portfolio_cost_krw(portfolio, exchange_rates)
            total_invested_krw += position_cost_krw
            
            # 현재가 및 전일 종가 가져오기
            current_price = None
            previous_close = None
            
            if self.toss_proxy_service:
                try:
                    # Toss API에서 실시간 가격 및 전일 종가 조회
                    stock_info = self.toss_proxy_service.get_stock_price(portfolio.product_code)
                    if stock_info:
                        current_price = Decimal(str(stock_info.get('current_price', 0)))
                        previous_close = Decimal(str(stock_info.get('previous_close', 0)))
                except Exception:
                    pass
            
            # 현재가가 없으면 평균가 사용
            if current_price is None:
                current_price = portfolio.average_price or Decimal('0')
            if previous_close is None:
                previous_close = current_price  # 전일 종가 정보가 없으면 현재가로 대체
            
            # 현재 가치 계산
            position_value = current_price * portfolio.current_quantity
            
            # 일간 손익 계산 (현재가 - 전일종가) * 수량
            daily_change = (current_price - previous_close) * portfolio.current_quantity
            
            # 해외 주식인 경우 캐싱된 환율 적용
            if portfolio.base_currency and portfolio.base_currency != 'KRW':
                exchange_rate = exchange_rates.get(portfolio.base_currency, Decimal('1'))
                position_value = position_value * exchange_rate
                daily_change = daily_change * exchange_rate
            
            total_current_value_krw += position_value
            daily_profit_loss_krw += daily_change
        
        # 총 수익금 및 수익률 계산
        total_profit_loss = total_current_value_krw - total_invested_krw
        total_profit_loss_rate = Decimal('0')
        if total_invested_krw > 0:
            total_profit_loss_rate = (total_profit_loss / total_invested_krw) * 100
        
        # 일간 손익률 계산
        daily_profit_loss_rate = Decimal('0')
        if total_invested_krw > 0:
            daily_profit_loss_rate = (daily_profit_loss_krw / total_invested_krw) * 100
        
        return {
            'total_invested_amount': float(total_invested_krw),
            'total_current_value': float(total_current_value_krw),
            'total_profit_loss': float(total_profit_loss),
            'total_profit_loss_rate': float(total_profit_loss_rate),
            'daily_profit_loss': float(daily_profit_loss_krw),
            'daily_profit_loss_rate': float(daily_profit_loss_rate)
        }
    
    def get_investment_weights(self, user_id: str, filter_type: str = 'total', sector: Optional[str] = None) -> Dict[str, Any]:
        """
        투자 비중 정보를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            filter_type: 필터 타입 (total/domestic/foreign/sector/sector_group)
            sector: 섹터명 (filter_type이 'sector'일 때 필수)
            
        Returns:
            투자 비중 정보
        """
        portfolios = self.portfolio_repo.get_by_user_id(user_id, only_active=True, include_orders=False)
        
        if not portfolios:
            return {
                'filter_type': filter_type,
                'sector_name': sector,
                'total_invested_amount': 0,
                'total_current_value': 0,
                'total_profit_loss': 0,
                'total_profit_loss_rate': 0,
                'items': [],
                'sector_items': None
            }
        
        # 환율 및 주가 정보 캐싱
        exchange_rates = self._cache_exchange_rates(portfolios)
        stock_prices = self._cache_stock_prices(portfolios)
        
        # 필터링된 포트폴리오 선택
        filtered_portfolios = []
        for portfolio in portfolios:
            if portfolio.current_quantity <= 0:
                continue
                
            # 필터 적용
            if filter_type == 'domestic':
                # 국내 주식: KRW 또는 KOSPI/KOSDAQ 시장
                if portfolio.base_currency == 'KRW' or portfolio.market in ['KOSPI', 'KOSDAQ', 'KONEX']:
                    filtered_portfolios.append(portfolio)
            elif filter_type == 'foreign':
                # 해외 주식: KRW가 아닌 통화
                if portfolio.base_currency and portfolio.base_currency != 'KRW' and portfolio.market not in ['KOSPI', 'KOSDAQ', 'KONEX']:
                    filtered_portfolios.append(portfolio)
            elif filter_type == 'sector':
                # 섹터별 필터링
                if sector:
                    portfolio_sector = portfolio.industry_display or portfolio.industry_code or '기타'
                    if portfolio_sector == sector:
                        filtered_portfolios.append(portfolio)
            else:  # total
                filtered_portfolios.append(portfolio)
        
        # 총 투자금액 및 평가금액 계산 (KRW 기준)
        total_invested_krw = Decimal('0')
        total_current_value_krw = Decimal('0')
        portfolio_investments = []
        
        for portfolio in filtered_portfolios:
            # 투자금액 계산 (KRW 기준)
            invested_krw = self._calculate_portfolio_cost_krw(portfolio, exchange_rates)
            
            # 현재 평가금액 계산 (KRW 기준)
            current_value_krw = self._calculate_portfolio_value_krw(portfolio, stock_prices, exchange_rates)
            
            portfolio_investments.append({
                'portfolio': portfolio,
                'invested_amount': invested_krw,
                'current_value': current_value_krw
            })
            total_invested_krw += invested_krw
            total_current_value_krw += current_value_krw
        
        # 투자 비중 계산 및 결과 생성
        items = []
        for item in portfolio_investments:
            portfolio = item['portfolio']
            invested_amount = item['invested_amount']
            current_value = item['current_value']
            
            # 평가 손익 및 수익률 계산
            profit_loss = current_value - invested_amount
            profit_loss_rate = Decimal('0')
            if invested_amount > 0:
                profit_loss_rate = (profit_loss / invested_amount) * 100
            
            # 투자 비중 계산
            weight_percentage = Decimal('0')
            if total_invested_krw > 0:
                weight_percentage = (invested_amount / total_invested_krw) * 100
            
            items.append({
                'product_code': portfolio.product_code,
                'product_name': portfolio.product_name or portfolio.product_code,
                'market': portfolio.market,
                'sector': portfolio.industry_display or portfolio.industry_code or '기타',
                'invested_amount': float(invested_amount),
                'current_value': float(current_value),
                'profit_loss': float(profit_loss),
                'profit_loss_rate': float(profit_loss_rate),
                'weight_percentage': float(weight_percentage),
                'quantity': float(portfolio.current_quantity),
                'average_price': float(portfolio.krw_average_price or portfolio.average_price or 0)
            })
        
        # 투자 비중 기준으로 정렬 (내림차순)
        items.sort(key=lambda x: x['weight_percentage'], reverse=True)
        
        # 섹터 그룹 모드일 경우 섹터별로 그룹화
        if filter_type == 'sector_group':
            sector_groups = {}
            
            for item in items:
                sector_name = item['sector']
                if sector_name not in sector_groups:
                    sector_groups[sector_name] = {
                        'sector': sector_name,
                        'invested_amount': Decimal('0'),
                        'current_value': Decimal('0'),
                        'stocks': []
                    }
                
                sector_groups[sector_name]['invested_amount'] += Decimal(str(item['invested_amount']))
                sector_groups[sector_name]['current_value'] += Decimal(str(item['current_value']))
                sector_groups[sector_name]['stocks'].append(item)
            
            # 섹터별 투자 비중 계산 및 정렬
            sector_items = []
            for sector_name, group_data in sector_groups.items():
                sector_invested = group_data['invested_amount']
                sector_current = group_data['current_value']
                sector_profit_loss = sector_current - sector_invested
                
                # 섹터별 수익률 계산
                sector_profit_loss_rate = Decimal('0')
                if sector_invested > 0:
                    sector_profit_loss_rate = (sector_profit_loss / sector_invested) * 100
                
                # 섹터별 투자 비중 계산
                weight_percentage = Decimal('0')
                if total_invested_krw > 0:
                    weight_percentage = (sector_invested / total_invested_krw) * 100
                
                sector_items.append({
                    'sector': sector_name,
                    'invested_amount': float(sector_invested),
                    'current_value': float(sector_current),
                    'profit_loss': float(sector_profit_loss),
                    'profit_loss_rate': float(sector_profit_loss_rate),
                    'weight_percentage': float(weight_percentage),
                    'stock_count': len(group_data['stocks']),
                    'stocks': group_data['stocks']
                })
            
            # 섹터별 투자 비중 기준으로 정렬
            sector_items.sort(key=lambda x: x['weight_percentage'], reverse=True)
            
            # 총 손익 계산
            total_profit_loss = total_current_value_krw - total_invested_krw
            total_profit_loss_rate = Decimal('0')
            if total_invested_krw > 0:
                total_profit_loss_rate = (total_profit_loss / total_invested_krw) * 100
            
            return {
                'filter_type': filter_type,
                'sector_name': None,
                'total_invested_amount': float(total_invested_krw),
                'total_current_value': float(total_current_value_krw),
                'total_profit_loss': float(total_profit_loss),
                'total_profit_loss_rate': float(total_profit_loss_rate),
                'items': None,
                'sector_items': sector_items
            }
        
        # 총 손익 계산
        total_profit_loss = total_current_value_krw - total_invested_krw
        total_profit_loss_rate = Decimal('0')
        if total_invested_krw > 0:
            total_profit_loss_rate = (total_profit_loss / total_invested_krw) * 100
        
        return {
            'filter_type': filter_type,
            'sector_name': sector,
            'total_invested_amount': float(total_invested_krw),
            'total_current_value': float(total_current_value_krw),
            'total_profit_loss': float(total_profit_loss),
            'total_profit_loss_rate': float(total_profit_loss_rate),
            'items': items,
            'sector_items': None
        }
