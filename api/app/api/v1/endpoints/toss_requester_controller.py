from typing import Optional, Dict, Any
import random
import json
import copy

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from app.config.get_current_user import get_current_user
from app.utils.response_helper import create_response


router = APIRouter()

# Toss API Base URLs
INFO_BASE_URL = "https://wts-info-api.tossinvest.com"
CERT_BASE_URL = "https://wts-cert-api.tossinvest.com"

USER_AGENTS = [
    # ===== Desktop (Windows/macOS/Linux) ~25 =====
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/125.0.0.0 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/126.0.0.0 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",

    # ===== Android Tablets ~25 =====
    "Mozilla/5.0 (Linux; Android 14; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel Tablet Build/AP1A.240505.004) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",  # Galaxy Tab S8
    "Mozilla/5.0 (Linux; Android 13; SM-X800) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # Galaxy Tab S8+
    "Mozilla/5.0 (Linux; Android 13; SM-X900) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",  # Galaxy Tab S8 Ultra
    "Mozilla/5.0 (Linux; Android 12; SM-T970) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",  # Galaxy Tab S7+
    "Mozilla/5.0 (Linux; Android 12; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",  # Galaxy Tab S7
    "Mozilla/5.0 (Linux; Android 12; SM-P610) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # Tab S6 Lite
    "Mozilla/5.0 (Linux; Android 14; SM-X810) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",  # Tab S9+
    "Mozilla/5.0 (Linux; Android 14; SM-X910) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",  # Tab S9 Ultra
    "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # Tab S9
    "Mozilla/5.0 (Linux; Android 13; Lenovo TB-X606F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Lenovo TB-8505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Lenovo TB-X705F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Xiaomi Pad 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Xiaomi Pad 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; OnePlus Pad) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Nexus 9 Build/LMY47X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Nexus 7 Build/JOP40D) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Tablet; SAMSUNG SM-X906N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Tablet; SAMSUNG SM-X706N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Tablet; HUAWEI MediaPad M6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Tablet; Lenovo TB-J706F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Tablet; Lenovo TB-X306F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Tablet; OPPO Pad 2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

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


async def _proxy_post(path: str, body: Optional[Dict] = None, base_url: str = None):
    """Generic POST proxy with configurable base URL"""
    if base_url is None:
        base_url = CERT_BASE_URL
    url = f"{base_url}{path}"
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "content-type": "application/json",
            "Origin": "https://www.tossinvest.com",
            "Referer": "https://www.tossinvest.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
        }
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.post(url, json=body)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream proxy error: {str(e)}")


async def _proxy_get(path: str, params: Optional[dict] = None, base_url: str = None):
    """Generic GET proxy with configurable base URL"""
    if base_url is None:
        base_url = INFO_BASE_URL
    url = f"{base_url}{path}"
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Origin": "https://www.tossinvest.com",
            "Referer": "https://www.tossinvest.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
        }
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream proxy error: {str(e)}")

# ===== 메인 페이지 관련 API =====
@router.get("/t/main/indicators", summary="메인 - 지수/환율")
async def proxy_main_indicators(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v2/dashboard/wts/overview/indicator/index", base_url=CERT_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/main/news-highlight", summary="메인 - 뉴스 하이라이트")
async def proxy_main_news_highlight(
    market: str = Query("all", description="시장 구분"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"market": market, "type": "highlight"}
    data = await _proxy_get("/api/v2/dashboard/wts/overview/news", params=params, base_url=CERT_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/main/hot-community", summary="메인 - 핫 커뮤니티")
async def proxy_main_hot_community(
    tag: str = Query("ALL", description="태그 필터"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"tag": tag}
    data = await _proxy_get("/api/v1/dashboard/wts/overview/hot-community", params=params, base_url=CERT_BASE_URL)
    return create_response(data, message="OK")


# ===== 지수 관련 API =====

@router.get("/t/index/nasdaq", summary="나스닥 현재가")
async def proxy_nasdaq_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/COMP.NAI")
    return create_response(data, message="OK")


@router.get("/t/index/nasdaq/chart", summary="나스닥 차트")
async def proxy_nasdaq_chart(
    period: str = Query("1d", description="기간 (1d, 5d, 1m, 3m, 6m, 1y, 3y, 5y, 10y)"),
    interval: str = Query("min:5", description="인터벌 (min:1, min:5, min:10, min:30, min:60, day:1)"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/COMP.NAI/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/index/sp500", summary="S&P 500 현재가")
async def proxy_sp500_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/SPX.CBI")
    return create_response(data, message="OK")


@router.get("/t/index/sp500/chart", summary="S&P 500 차트")
async def proxy_sp500_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/SPX.CBI/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/index/kospi", summary="코스피 현재가")
async def proxy_kospi_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/KGG01P")
    return create_response(data, message="OK")


@router.get("/t/index/kospi/chart", summary="코스피 차트")
async def proxy_kospi_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/kr-s/KGG01P/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/index/kosdaq", summary="코스닥 현재가")
async def proxy_kosdaq_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/QGG01P")
    return create_response(data, message="OK")


@router.get("/t/index/kosdaq/chart", summary="코스닥 차트")
async def proxy_kosdaq_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/kr-s/QGG01P/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/index/vix", summary="VIX 현재가")
async def proxy_vix_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/RGI..VIX")
    return create_response(data, message="OK")


@router.get("/t/index/vix/chart", summary="VIX 차트")
async def proxy_vix_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/RGI..VIX/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 환율 관련 API =====

@router.get("/t/exchange-rate", summary="환율 정보")
async def proxy_exchange_rate(
    buyCurrency: str = Query("USD", description="매수 통화"),
    sellCurrency: str = Query("KRW", description="매도 통화"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "buyCurrency": buyCurrency,
        "sellCurrency": sellCurrency
    }
    data = await _proxy_get("/api/v1/product/exchange-rate", params=params)
    return create_response(data, message="OK")


@router.get("/t/exchange-rate/chart", summary="환율 차트")
async def proxy_exchange_rate_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    currency: str = Query("USD", description="통화"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    useAdjustedRate: bool = Query(True, description="조정 환율 사용 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "last": str(last).lower(),
        "useAdjustedRate": str(useAdjustedRate).lower(),
        "currency": currency
    }
    data = await _proxy_get(f"/api/v1/r-chart/fx/EXCHANGE_RATE/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 원자재 관련 API =====

@router.get("/t/commodity/gold", summary="금 현재가")
async def proxy_gold_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/RFU.GCv1")
    return create_response(data, message="OK")


@router.get("/t/commodity/gold/chart", summary="금 차트")
async def proxy_gold_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/RFU.GCv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/commodity/silver", summary="은 현재가")
async def proxy_silver_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/RFU.SIv1")
    return create_response(data, message="OK")


@router.get("/t/commodity/silver/chart", summary="은 차트")
async def proxy_silver_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/RFU.SIv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/commodity/wti", summary="WTI 원유 현재가")
async def proxy_wti_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/RFU.CLv1")
    return create_response(data, message="OK")


@router.get("/t/commodity/wti/chart", summary="WTI 원유 차트")
async def proxy_wti_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/RFU.CLv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


@router.get("/t/commodity/copper", summary="구리 현재가")
async def proxy_copper_price(
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get("/api/v1/index-prices/RFU.HGv1")
    return create_response(data, message="OK")


@router.get("/t/commodity/copper/chart", summary="구리 차트")
async def proxy_copper_chart(
    period: str = Query("1d", description="기간"),
    interval: str = Query("min:5", description="인터벌"),
    session: str = Query("main", description="세션"),
    investMode: str = Query("krx", description="투자 모드"),
    last: bool = Query(False, description="마지막 데이터 여부"),
    current_user_id: str = Depends(get_current_user)
):
    params = {
        "session": session,
        "investMode": investMode,
        "last": str(last).lower()
    }
    data = await _proxy_get(f"/api/v1/r-chart/us-s/RFU.HGv1/{period}/{interval}", params=params)
    return create_response(data, message="OK")


# ===== 검색 관련 API =====

@router.post("/t/search/auto-complete", summary="검색 자동완성")
async def proxy_search_auto_complete(
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
    current_user_id: str = Depends(get_current_user)
):
    body = {
        "query": query,
        "sections": sections
    }
    data = await _proxy_post("/api/v3/search-all/wts-auto-complete", body=body, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 종목 관련 API =====

@router.get("/t/stock-infos/{productCode}", summary="종목 기본정보")
async def proxy_stock_info(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    # v2 stock-infos requires 'A' prefix
    data = await _proxy_get(f"/api/v2/stock-infos/{productCode}")
    return create_response(data, message="OK")


@router.get("/t/news/companies/{companyCode}", summary="종목 뉴스")
async def proxy_stock_news(
    companyCode: str,
    size: int = Query(20, ge=1, le=100),
    order_by: str = Query("latest"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"size": size, "orderBy": order_by}
    data = await _proxy_get(f"/api/v2/news/companies/{companyCode}", params=params)
    return create_response(data, message="OK")


@router.get("/t/dart-reports/companies/wts/{companyCode}", summary="종목 공시")
async def proxy_dart_reports(
    companyCode: str,
    size: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user)
):
    params = {"size": size}
    data = await _proxy_get(f"/api/v2/dart-reports/companies/wts/{companyCode}", params=params)
    return create_response(data, message="OK")


@router.get("/t/stock-prices/details", summary="종목 거래 현황")
async def proxy_price_details(
    productCode: str = Query(..., description="종목 코드"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"productCodes": f"{productCode}"}
    data = await _proxy_get("/api/v3/stock-prices/details", params=params)
    return create_response(data, message="OK")


@router.get("/t/mds/broker/trading-ranking", summary="종목 매수/매도 상위 (미장은 정보 없음)")
async def proxy_top_broker(
    productCode: str = Query(..., description="종목 코드"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"code": f"{productCode}"}
    data = await _proxy_get("/api/v1/mds/broker/trading-ranking", params=params)
    return create_response(data, message="OK")


@router.get("/t/stock-infos/trade/trend/trading-trend", summary="투자자별 매매 동향 (미장은 정보 없음)")
async def proxy_trade_trend(
    productCode: str = Query(..., description="종목 코드", alias="productCode"),
    size: int = Query(50, ge=1, le=200),
    current_user_id: str = Depends(get_current_user)
):
    params = {"productCode": f"{productCode}", "size": size}
    data = await _proxy_get("/api/v1/stock-infos/trade/trend/trading-trend", params=params)
    return create_response(data, message="OK")


# ===== 종목 상세 - 주요정보 관련 API =====

@router.get("/t/stock-infos/{productCode}/overview", summary="종목 - 주요정보")
async def proxy_stock_overview(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v2/stock-infos/{productCode}/overview")
    return create_response(data, message="OK")


@router.get("/t/companies/{companyCode}/sales-compositions", summary="종목 - 매출·산업 구성")
async def proxy_stock_sales_compositions(
    companyCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v1/companies/{companyCode}/sales-compositions")
    return create_response(data, message="OK")

@router.get("/t/companies/{companyCode}/tics", summary="종목 - 주요 산업")
async def proxy_stock_tics(
    companyCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v2/companies/{companyCode}/tics")
    return create_response(data, message="OK")

@router.get("/t/stock-detail/ui/wts/{productCode}/investment-indicators", summary="종목 - 투자 지표")
async def proxy_stock_investment_indicators(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/investment-indicators")
    return create_response(data, message="OK")


@router.get("/t/stock-infos/operating-income/{productCode}", summary="종목 - 수익성")
async def proxy_stock_operating_income(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/stock-infos/operating-income/{productCode}", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/stock-infos/stability/{productCode}", summary="종목 - 안정성")
async def proxy_stock_stability(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/stock-infos/stability/{productCode}", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/stock-infos/revenue-and-net-profit/{productCode}", summary="종목 - 영업이익 성장률")
async def proxy_stock_revenue_and_net_profit(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/stock-infos/revenue-and-net-profit/{productCode}", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/companies/{productCode}/financial-statement-records", summary="종목 - 손익계산서")
async def proxy_stock_income_statement(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/companies/{productCode}/financial-statement-records", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")

@router.post("/t/companies/{productCode}/financial-statements/comprehensive", summary="종목 - 재무상태표")
async def proxy_stock_balance_sheet(
    productCode: str,
    body: Optional[Dict] = Body(None),
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/companies/{productCode}/financial-statements/comprehensive", body=body, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


@router.get("/t/companies/{productCode}/financial/estimate/revenue", summary="종목 - 실적")
async def proxy_stock_estimate_revenue(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/companies/{productCode}/financial/estimate/revenue", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 종목 상세 - 애널리스트 분석 관련 API =====

@router.get("/t/stock-detail/ui/wts/{productCode}/analyst-reports", summary="종목 - 애널리스트 분석")
async def proxy_stock_analyst_reports(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/analyst-reports")
    return create_response(data, message="OK")


@router.get("/t/stock-detail/ui/wts/{productCode}/analyst-opinion", summary="종목 - 애널리스트 의견")
async def proxy_stock_analyst_opinion(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_get(f"/api/v1/stock-detail/ui/wts/{productCode}/analyst-opinion")
    return create_response(data, message="OK")


@router.get("/t/stock-infos/evaluation-comparison/{productCode}", summary="종목 - 투자 지표(PER...)")
async def proxy_stock_evaluation_comparison(
    productCode: str,
    current_user_id: str = Depends(get_current_user)
):
    data = await _proxy_post(f"/api/v2/stock-infos/evaluation-comparison/{productCode}", body={}, base_url=INFO_BASE_URL)
    return create_response(data, message="OK")


# ===== 스크리너 API =====

@router.get("/screener/categories", summary="주식 스크리너 카테고리 목록 조회")
async def get_screener_categories(current_user_id: str = Depends(get_current_user)):
    categories = {key: value["name"] for key, value in SCREENER_CATEGORIES.items()}
    return create_response(categories, message="OK")


@router.get("/screener/screen/{category_key}", summary="카테고리별 주식 스크리닝 실행")
async def run_screener_by_category(
    category_key: str,
    nation: str = Query("kr", description="국가 코드 (kr, us)"),
    current_user_id: str = Depends(get_current_user)
):
    if category_key not in SCREENER_CATEGORIES:
        raise HTTPException(status_code=404, detail="Category not found")
    
    payload = copy.deepcopy(SCREENER_CATEGORIES[category_key]["payload"])
    payload["nation"] = nation
    data = await _proxy_post("/api/v2/screener/screen", body=payload)
    return create_response(data, message="OK")

# @router.post("/screener/custom", summary="사용자 정의 주식 스크리닝 실행")
# async def run_screener_custom(
#     payload: Dict[str, Any] = Body(...),
#     current_user_id: str = Depends(get_current_user)
# ):
#     data = await _proxy_post("/api/v2/screener/screen", body=payload)
#     return create_response(data, message="OK")

