from typing import Optional, Dict, Any
import json
import copy

from fastapi import APIRouter, Depends, HTTPException, Query, Body

from app.config.get_current_user import get_current_user
from app.config.di import get_toss_proxy_service
from app.services.toss_proxy_service import TossProxyService
from app.utils.response_helper import create_response
from app.api.v1.schemas.stock_schemas import StockPriceDetailsResponse


router = APIRouter()

def _assert_product_code(product_code: str):
    if not (isinstance(product_code, str) and (product_code.startswith('US') or product_code.startswith('A'))):
        raise HTTPException(status_code=400, detail="product_code는 'US' 또는 'A'로 시작해야 합니다")


# <주식 골라보기 목록>
SCREENER_CATEGORIES = {
    "undervalued_escape": {
        "name": "저평가탈출",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1,"includeFrom":True,"includeTo":True}}]},{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":20,"numberOfWeeks":52}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "growth_potential": {
        "name": "성장기대주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"}}
    },
    "undervalued_growth": {
        "name": "저평가 성장주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":20,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"}}
    },
    "consecutive_rise": {
        "name": "연속상승세",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "steady_dividend": {
        "name": "꾸준한 배당주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_성향","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.3,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_연속_증가","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"}}
    },
    "high_profit_undervalued": {
        "name": "고수익 저평가",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    },
    "high_roe_low_pbr": {
        "name": "고ROE 저PBR",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    },
    "accelerated_profit_growth": {
        "name": "이익 가속 성장주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"}}
    },
    "strong_momentum_short_term": {
        "name": "모멘텀 강한 종목(단기 상승)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "value_momentum": {
        "name": "가치 모멘텀(저PER + 상승 전환)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":12,"includeFrom":True,"includeTo":True}}]},{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "new_high_trend": {
        "name": "신고가 추세 지속(최근 10일 내 52주 신고가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":10,"numberOfWeeks":52}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "dividend_growth_hybrid": {
        "name": "배당 + 성장 하이브리드",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"}}
    },
    "turnaround_candidate": {
        "name": "턴어라운드 후보(이익 회복)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"}}
    },
    "quality_profit_growth": {
        "name": "질적 수익 성장(ROE 개선 + 연속 증가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_연속_증가","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    },
    "excellent_dividend": {
        "name": "배당 우수(안정성)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_성향","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.4,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.02,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"}}
    },
    "correction_rebound": {
        "name": "눌림목 반등 후보(성장 기초 + 단기 조정)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":-0.05,"to":0,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "high_growth_low_pbr": {
        "name": "고성장 저PBR",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.2,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"}}
    },
    "low_per_stable_growth": {
        "name": "저PER 안정 성장",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":12,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "high_roe_low_per_combo": {
        "name": "고ROE 저PER 콤보",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":15,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    },
    "midcap_growth_momentum": {
        "name": "중형주 성장 모멘텀(단기 2주)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"WEEK_2"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "week52_low_rebound": {
        "name": "52주 저점 반등주(최근 20일)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":20,"numberOfWeeks":-52}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "stable_dividend_4plus": {
        "name": "안정적 배당(배당률 4%+, 연속 5년+)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.04,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"}}
    },
    "profit_recovery": {
        "name": "수익성 회복(순이익 TTM+, 분기+)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"}}
    },
    "low_pbr_dividend": {
        "name": "저PBR + 배당(가치/현금흐름)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.0,"includeFrom":True,"includeTo":True}}]},{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.025,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "steady_revenue_growth": {
        "name": "꿈준한 매출 성장(보수적)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"}}
    },
    "per_normalization": {
        "name": "PER 밸류에이션 정상화(리레이팅)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":20,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "roe_improving": {
        "name": "ROE 개선 중(최근 TTM)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.08,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    },
    "quarter_momentum": {
        "name": "분기 모멘텀(5일 수익률 +)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.02,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "turnaround_early": {
        "name": "턴어라운드 초기(매출/이익 동시 개선)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"}}
    },
    "conservative_value": {
        "name": "보수적 가치주(PER/PBR 동시 저평가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.0,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"}}
    },
    "medium_term_momentum": {
        "name": "중장기 모멘텀(1개월 +)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"MONTH_1"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"}}
    },
    "ai_stable_growth_value": {
        "name": "AI 추천 안정 성장 가치주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":15,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.5,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.10,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.10,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"}}
    }
}




# ===== 메인 페이지 관련 API =====
@router.get("/main/indicators", summary="메인 - 지수/환율")
def proxy_main_indicators(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v2/dashboard/wts/overview/indicator/index", base_url=toss_proxy_service.CERT_BASE_URL)
    return create_response(data, message="OK")


@router.get("/main/news-highlight", summary="메인 - 뉴스 하이라이트")
def proxy_main_news_highlight(
    market: str = Query("all", description="시장 구분"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {"market": market, "type": "highlight"}
    data = toss_proxy_service.proxy_get("/api/v2/dashboard/wts/overview/news", params=params, base_url=toss_proxy_service.CERT_BASE_URL)
    return create_response(data, message="OK")


@router.get("/main/hot-community", summary="메인 - 핫 커뮤니티")
def proxy_main_hot_community(
    tag: str = Query("ALL", description="태그 필터"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {"tag": tag}
    data = toss_proxy_service.proxy_get("/api/v1/dashboard/wts/overview/hot-community", params=params, base_url=toss_proxy_service.CERT_BASE_URL)
    return create_response(data, message="OK")


# ===== 지수 관련 API =====

@router.get("/index/nasdaq", summary="나스닥 현재가")
def proxy_nasdaq_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/COMP.NAI")
    return create_response(data, message="OK")


@router.get("/index/nasdaq/chart", summary="나스닥 차트")
def proxy_nasdaq_chart(
    period: str = Query("1d", description="기간 (1d, 5d, 1m, 3m, 6m, 1y, 3y, 5y, 10y)"),
    interval: str = Query("min:5", description="인터벌 (min:1, min:5, min:10, min:30, min:60, day:1)"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/COMP.NAI/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/index/sp500", summary="S&P 500 현재가")
def proxy_sp500_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/SPX.CBI")
    return create_response(data, message="OK")


@router.get("/index/sp500/chart", summary="S&P 500 차트")
def proxy_sp500_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/SPX.CBI/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/index/kospi", summary="코스피 현재가")
def proxy_kospi_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/KGG01P")
    return create_response(data, message="OK")


@router.get("/index/kospi/chart", summary="코스피 차트")
def proxy_kospi_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/kr-s/KGG01P/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/index/kosdaq", summary="코스닥 현재가")
def proxy_kosdaq_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/QGG01P")
    return create_response(data, message="OK")


@router.get("/index/kosdaq/chart", summary="코스닥 차트")
def proxy_kosdaq_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/kr-s/QGG01P/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/index/vix", summary="VIX 현재가")
def proxy_vix_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/RGI..VIX")
    return create_response(data, message="OK")


@router.get("/index/vix/chart", summary="VIX 차트")
def proxy_vix_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/RGI..VIX/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 환율 관련 API =====

@router.get("/exchange-rate", summary="환율 정보")
def proxy_exchange_rate(
    buyCurrency: str = Query("USD", description="매수 통화"),
    sellCurrency: str = Query("KRW", description="매도 통화"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "buyCurrency": buyCurrency,
        "sellCurrency": sellCurrency
    }
    data = toss_proxy_service.proxy_get("/api/v1/product/exchange-rate", params=params)
    return create_response(data, message="OK")


@router.get("/exchange-rate/chart", summary="환율 차트")
def proxy_exchange_rate_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    currency: str = Query("USD", description="통화"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    useAdjustedRate: bool = Query(True, description="조정 환율 사용 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "last": str(last).lower(),
        "useAdjustedRate": str(useAdjustedRate).lower(),
        "currency": currency
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/fx/EXCHANGE_RATE/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 원자재 관련 API =====

@router.get("/commodity/gold", summary="금 현재가")
def proxy_gold_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/RFU.GCv1")
    return create_response(data, message="OK")


@router.get("/commodity/gold/chart", summary="금 차트")
def proxy_gold_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/RFU.GCv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/commodity/silver", summary="은 현재가")
def proxy_silver_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/RFU.SIv1")
    return create_response(data, message="OK")


@router.get("/commodity/silver/chart", summary="은 차트")
def proxy_silver_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/RFU.SIv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/commodity/wti", summary="WTI 원유 현재가")
def proxy_wti_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/RFU.CLv1")
    return create_response(data, message="OK")


@router.get("/commodity/wti/chart", summary="WTI 원유 차트")
def proxy_wti_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/RFU.CLv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/commodity/copper", summary="구리 현재가")
def proxy_copper_price(
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get("/api/v1/index-prices/RFU.HGv1")
    return create_response(data, message="OK")


@router.get("/commodity/copper/chart", summary="구리 차트")
def proxy_copper_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = toss_proxy_service.proxy_get(f"/api/v1/r-chart/us-s/RFU.HGv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 검색 관련 API =====

@router.post("/search/auto-complete", summary="검색 자동완성")
def proxy_search_auto_complete(
    query: str = Body(..., description="검색어"),
    sections: Optional[list] = Body(
        default=[
            {"type": "SCREENER"},
            {"type": "NEWS"},
            {"type": "PRODUCT", "option": {"addIntegratedSearchResult": True}},
            {"type": "TICS"}
        ],
        description="검색 섹션 설정"
    ),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    body = {
        "query": query,
        "sections": sections
    }
    data = toss_proxy_service.proxy_post("/api/v3/search-all/wts-auto-complete", body=body, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 종목 관련 API =====

@router.get("/stock-infos/{productCode}", summary="종목 기본정보")
def proxy_stock_info(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    # v2 stock-infos requires 'A' prefix
    data = toss_proxy_service.get_stock_info(productCode)
    return create_response(data, message="OK")


@router.get("/news/companies/{companyCode}", summary="종목 뉴스")
def proxy_stock_news(
    companyCode: str,
    size: int = Query(20, ge=1, le=100),
    order_by: str = Query("latest"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {"size": size, "orderBy": order_by}
    data = toss_proxy_service.proxy_get(f"/api/v2/news/companies/{companyCode}", params=params)
    return create_response(data, message="OK")


@router.get("/dart-reports/companies/wts/{companyCode}", summary="종목 공시")
def proxy_dart_reports(
    companyCode: str,
    size: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    params = {"size": size}
    data = toss_proxy_service.proxy_get(f"/api/v2/dart-reports/companies/wts/{companyCode}", params=params)
    return create_response(data, message="OK")


@router.get("/stock-prices/details", summary="종목 거래 현황")
def proxy_price_details(
    productCode: str = Query(..., description="종목 코드"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    """
    종목의 상세 거래 현황을 조회합니다.
    
    - **productCode**: 종목 코드 (예: A456160)
    - **Returns**: StockPriceDetailsResponse 형태의 응답
    """
    _assert_product_code(productCode)
    params = {"productCodes": f"{productCode}"}
    data = toss_proxy_service.proxy_get("/api/v3/stock-prices/details", params=params)
    return create_response(data, message="OK")


@router.get("/mds/broker/trading-ranking", summary="종목 매수/매도 상위 (미장은 정보 없음)")
def proxy_top_broker(
    productCode: str = Query(..., description="종목 코드"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    params = {"code": f"{productCode}"}
    data = toss_proxy_service.proxy_get("/api/v1/mds/broker/trading-ranking", params=params)
    return create_response(data, message="OK")


@router.get("/stock-infos/trade/trend/trading-trend", summary="투자자별 매매 동향 (미장은 정보 없음)")
def proxy_trade_trend(
    productCode: str = Query(..., description="종목 코드", alias="productCode"),
    size: int = Query(50, ge=1, le=200),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    params = {"productCode": f"{productCode}", "size": size}
    data = toss_proxy_service.proxy_get("/api/v1/stock-infos/trade/trend/trading-trend", params=params)
    return create_response(data, message="OK")


# ===== 종목 상세 - 주요정보 관련 API =====

@router.get("/stock-infos/{productCode}/overview", summary="종목 - 주요정보")
def proxy_stock_overview(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_get(f"/api/v2/stock-infos/{productCode}/overview")
    return create_response(data, message="OK")


@router.get("/companies/{companyCode}/sales-compositions", summary="종목 - 매출·산업 구성")
def proxy_stock_sales_compositions(
    companyCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get(f"/api/v1/companies/{companyCode}/sales-compositions")
    return create_response(data, message="OK")

@router.get("/companies/{companyCode}/tics", summary="종목 - 주요 산업")
def proxy_stock_tics(
    companyCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    data = toss_proxy_service.proxy_get(f"/api/v2/companies/{companyCode}/tics")
    return create_response(data, message="OK")

@router.get("/stock-detail/ui/wts/{productCode}/investment-indicators", summary="종목 - 투자 지표")
def proxy_stock_investment_indicators(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/investment-indicators")
    return create_response(data, message="OK")


@router.get("/stock-infos/operating-income/{productCode}", summary="종목 - 수익성")
def proxy_stock_operating_income(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/stock-infos/operating-income/{productCode}", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/stock-infos/stability/{productCode}", summary="종목 - 안정성")
def proxy_stock_stability(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/stock-infos/stability/{productCode}", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/stock-infos/revenue-and-net-profit/{productCode}", summary="종목 - 영업이익 성장률")
def proxy_stock_revenue_and_net_profit(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/stock-infos/revenue-and-net-profit/{productCode}", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/companies/{productCode}/financial-statement-records", summary="종목 - 손익계산서")
def proxy_stock_income_statement(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/companies/{productCode}/financial-statement-records", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")

@router.post("/companies/{productCode}/financial-statements/comprehensive", summary="종목 - 재무상태표")
def proxy_stock_balance_sheet(
    productCode: str,
    body: Optional[Dict] = Body(None),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/companies/{productCode}/financial-statements/comprehensive", body=body, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/companies/{productCode}/financial/estimate/revenue", summary="종목 - 실적")
def proxy_stock_estimate_revenue(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/companies/{productCode}/financial/estimate/revenue", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 종목 상세 - 애널리스트 분석 관련 API =====

@router.get("/stock-detail/ui/wts/{productCode}/analyst-reports", summary="종목 - 애널리스트 분석")
def proxy_stock_analyst_reports(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/analyst-reports")
    return create_response(data, message="OK")


@router.get("/stock-detail/ui/wts/{productCode}/analyst-opinion", summary="종목 - 애널리스트 의견")
def proxy_stock_analyst_opinion(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/analyst-opinion")
    return create_response(data, message="OK")


@router.get("/stock-infos/evaluation-comparison/{productCode}", summary="종목 - 투자 지표(PER...)")
def proxy_stock_evaluation_comparison(
    productCode: str,
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    _assert_product_code(productCode)
    data = toss_proxy_service.proxy_post(f"/api/v2/stock-infos/evaluation-comparison/{productCode}", body={}, base_url=toss_proxy_service.INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 스크리너 API =====

@router.get("/screener/categories", summary="주식 스크리너 카테고리 목록 조회")
def get_screener_categories(current_user_id: str = Depends(get_current_user)):
    categories = {key: value["name"] for key, value in SCREENER_CATEGORIES.items()}
    return create_response(categories, message="OK")


@router.get("/screener/screen/{category_key}", summary="카테고리별 주식 스크리닝 실행")
def run_screener_by_category(
    category_key: str,
    nation: str = Query("kr", description="국가 코드 (kr, us)"),
    current_user_id: str = Depends(get_current_user),
    toss_proxy_service: TossProxyService = Depends(get_toss_proxy_service)
):
    if category_key not in SCREENER_CATEGORIES:
        raise HTTPException(status_code=404, detail="Category not found")
    
    payload = copy.deepcopy(SCREENER_CATEGORIES[category_key]["payload"])
    payload["nation"] = nation
    data = toss_proxy_service.proxy_post("/api/v2/screener/screen", body=payload)
    return create_response(data, message="OK")

# @router.post("/screener/custom", summary="사용자 정의 주식 스크리닝 실행")
# def run_screener_custom(
#     payload: Dict[str, Any] = Body(...),
#     current_user_id: str = Depends(get_current_user)
# ):
#     data = await _proxy_post("/api/v2/screener/screen", body=payload)
#     return create_response(data, message="OK")

