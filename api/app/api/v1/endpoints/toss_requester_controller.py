from typing import Optional, Dict, Any
import random
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from app.config.get_current_user import get_current_user
from app.utils.response_helper import create_response


router = APIRouter()

BASE_URL = "https://wts-info-api.tossinvest.com"

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

CERT_BASE_URL = "https://wts-cert-api.tossinvest.com"

# <주식 골라보기 목록>
SCREENER_CATEGORIES = {
    "undervalued_escape": {
        "name": "저평가탈출",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1,"includeFrom":True,"includeTo":True}}]},{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":20,"numberOfWeeks":52}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "growth_potential": {
        "name": "성장기대주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"},"nation":"kr"}
    },
    "undervalued_growth": {
        "name": "저평가 성장주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":20,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"},"nation":"kr"}
    },
    "consecutive_rise": {
        "name": "연속상승세",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "steady_dividend": {
        "name": "꾸준한 배당주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_성향","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.3,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_연속_증가","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"},"nation":"kr"}
    },
    "high_profit_undervalued": {
        "name": "고수익 저평가",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    },
    "high_roe_low_pbr": {
        "name": "고ROE 저PBR",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    },
    "accelerated_profit_growth": {
        "name": "이익 가속 성장주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"},"nation":"kr"}
    },
    "strong_momentum_short_term": {
        "name": "모멘텀 강한 종목(단기 상승)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "value_momentum": {
        "name": "가치 모멘텀(저PER + 상승 전환)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":12,"includeFrom":True,"includeTo":True}}]},{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "new_high_trend": {
        "name": "신고가 추세 지속(최근 10일 내 52주 신고가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":10,"numberOfWeeks":52}}]},{"id":"주가_연속_상승","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "dividend_growth_hybrid": {
        "name": "배당 + 성장 하이브리드",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"},"nation":"kr"}
    },
    "turnaround_candidate": {
        "name": "턴어라운드 후보(이익 회복)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"},"nation":"kr"}
    },
    "quality_profit_growth": {
        "name": "질적 수익 성장(ROE 개선 + 연속 증가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_연속_증가","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":2,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    },
    "excellent_dividend": {
        "name": "배당 우수(안정성)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_성향","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.4,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.02,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"},"nation":"kr"}
    },
    "correction_rebound": {
        "name": "눌림목 반등 후보(성장 기초 + 단기 조정)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":-0.05,"to":0,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "high_growth_low_pbr": {
        "name": "고성장 저PBR",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.2,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"},"nation":"kr"}
    },
    "low_per_stable_growth": {
        "name": "저PER 안정 성장",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":12,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.1,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "high_roe_low_per_combo": {
        "name": "고ROE 저PER 콤보",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.2,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":15,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    },
    "midcap_growth_momentum": {
        "name": "중형주 성장 모멘텀(단기 2주)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"WEEK_2"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "week52_low_rebound": {
        "name": "52주 저점 반등주(최근 20일)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"CUSTOM_N주_신고가_달성_경과일","conditions":[{"id":"WEEK_NEW_PRICE_HIT","type":"WEEK_NEW_PRICE_HIT_WITHIN","value":{"within":20,"numberOfWeeks":-52}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "stable_dividend_4plus": {
        "name": "안정적 배당(배당률 4%+, 연속 5년+)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.04,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_배당수익률","label":"배당수익률","order":"DESC"},"nation":"kr"}
    },
    "profit_recovery": {
        "name": "수익성 회복(순이익 TTM+, 분기+)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균순이익증감률_3Y","label":"연평균 순이익 증감률","order":"DESC"},"nation":"kr"}
    },
    "low_pbr_dividend": {
        "name": "저PBR + 배당(가치/현금흐름)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.0,"includeFrom":True,"includeTo":True}}]},{"id":"배당_수익률","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.025,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "steady_revenue_growth": {
        "name": "꿈준한 매출 성장(보수적)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"},"nation":"kr"}
    },
    "per_normalization": {
        "name": "PER 밸류에이션 정상화(리레이팅)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":5,"to":20,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "roe_improving": {
        "name": "ROE 개선 중(최근 TTM)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.08,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    },
    "quarter_momentum": {
        "name": "분기 모멘텀(5일 수익률 +)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"DAY_5"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.02,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "turnaround_early": {
        "name": "턴어라운드 초기(매출/이익 동시 개선)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.05,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"순이익_증감률","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"QUARTER"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_연평균매출액증감률_3Y","label":"연평균 매출액 증감률","order":"DESC"},"nation":"kr"}
    },
    "conservative_value": {
        "name": "보수적 가치주(PER/PBR 동시 저평가)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":10,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.0,"includeFrom":True,"includeTo":True}}]}],"sort":{"column":"C_PER","label":"PER","order":"ASC"},"nation":"kr"}
    },
    "medium_term_momentum": {
        "name": "중장기 모멘텀(1개월 +)",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"주가등락률","conditions":[{"id":"기간_선택_DAY_TO_MONTH","type":"PERIOD","value":"MONTH_1"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.03,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_주가등락률_1W","label":"주가등락률","order":"DESC"},"nation":"kr"}
    },
    "ai_stable_growth_value": {
        "name": "AI 추천 안정 성장 가치주",
        "payload": {"pagingParam":{"key":None,"number":1,"size":50},"filters":[{"id":"PER","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":15,"includeFrom":True,"includeTo":True}}]},{"id":"PBR","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0,"to":1.5,"includeFrom":True,"includeTo":True}}]},{"id":"연평균_매출액_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.10,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"연평균_순이익_증감률","conditions":[{"id":"기간_선택_TTM3_TTM5","type":"PERIOD","value":"TTM_3"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.10,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"ROE","conditions":[{"id":"기간_선택_QUARTER_TTM","type":"PERIOD","value":"TTM"},{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":0.15,"to":None,"includeFrom":True,"includeTo":None}}]},{"id":"배당_연속_지급_년수","conditions":[{"id":"NUMBER_RANGE_DEFAULT","type":"NUMBER_RANGE","value":{"from":3,"to":None,"includeFrom":True,"includeTo":None}}]}],"sort":{"column":"C_ROE_TTM","label":"ROE","order":"DESC"},"nation":"kr"}
    }
}


async def _proxy_post(path: str, body: Optional[Dict] = None):
    url = f"{CERT_BASE_URL}{path}"
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "content-type": "application/json",
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


async def _proxy_get(path: str, params: Optional[dict] = None):
    url = f"{BASE_URL}{path}"
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(url, params=params)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream proxy error: {str(e)}")


@router.get("/proxy/stock/{code}", summary="종목 기본정보 프록시")
async def proxy_stock_info(
    code: str,
    current_user_id: str = Depends(get_current_user)
):
    # v2 stock-infos requires 'A' prefix
    data = await _proxy_get(f"/api/v2/stock-infos/A{code}")
    return create_response(data, message="OK")


@router.get("/proxy/news/{code}", summary="종목 뉴스 프록시")
async def proxy_stock_news(
    code: str,
    size: int = Query(20, ge=1, le=100),
    order_by: str = Query("latest"),
    current_user_id: str = Depends(get_current_user)
):
    params = {"size": size, "orderBy": order_by}
    data = await _proxy_get(f"/api/v2/news/companies/{code}", params=params)
    return create_response(data, message="OK")


@router.get("/proxy/dart/{code}", summary="종목 공시 프록시")
async def proxy_dart_reports(
    code: str,
    size: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user)
):
    params = {"size": size}
    data = await _proxy_get(f"/api/v2/dart-reports/companies/wts/{code}", params=params)
    return create_response(data, message="OK")


@router.get("/proxy/price-details/{code}", summary="종목 거래 현황 프록시")
async def proxy_price_details(
    code: str,
    current_user_id: str = Depends(get_current_user)
):
    params = {"productCodes": f"A{code}"}
    data = await _proxy_get("/api/v3/stock-prices/details", params=params)
    return create_response(data, message="OK")


@router.get("/proxy/top-broker/{code}", summary="종목 매수/매도 상위 프록시")
async def proxy_top_broker(
    code: str,
    current_user_id: str = Depends(get_current_user)
):
    params = {"code": f"A{code}"}
    data = await _proxy_get("/api/v1/mds/broker/trading-ranking", params=params)
    return create_response(data, message="OK")


@router.get("/proxy/trade-trend/{code}", summary="투자자별 매매 동향 프록시")
async def proxy_trade_trend(
    code: str,
    size: int = Query(50, ge=1, le=200),
    current_user_id: str = Depends(get_current_user)
):
    params = {"productCode": f"A{code}", "size": size}
    data = await _proxy_get("/api/v1/stock-infos/trade/trend/trading-trend", params=params)
    return create_response(data, message="OK")


@router.get("/screener/categories", summary="주식 스크리너 카테고리 목록 조회")
async def get_screener_categories(current_user_id: str = Depends(get_current_user)):
    categories = {key: value["name"] for key, value in SCREENER_CATEGORIES.items()}
    return create_response(categories, message="OK")


@router.get("/screener/{category_key}", summary="카테고리별 주식 스크리닝 실행")
async def run_screener_by_category(
    category_key: str,
    current_user_id: str = Depends(get_current_user)
):
    if category_key not in SCREENER_CATEGORIES:
        raise HTTPException(status_code=404, detail="Category not found")
    
    payload = SCREENER_CATEGORIES[category_key]["payload"]
    data = await _proxy_post("/api/v2/screener/screen", body=payload)
    return create_response(data, message="OK")

# @router.post("/screener/custom", summary="사용자 정의 주식 스크리닝 실행")
# async def run_screener_custom(
#     payload: Dict[str, Any] = Body(...),
#     current_user_id: str = Depends(get_current_user)
# ):
#     data = await _proxy_post("/api/v2/screener/screen", body=payload)
#     return create_response(data, message="OK")


