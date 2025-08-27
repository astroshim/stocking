#!/usr/bin/env python3
"""
동적 구독 테스트 스크립트
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000/api/v1/admin"
HEADERS = {"Authorization": "Bearer test_token"}  # 임시 토큰

def test_dynamic_subscription():
    print("🧪 Testing dynamic subscription...")
    
    # 1. 현재 구독 목록 조회
    print("\n1. Getting current subscriptions...")
    response = requests.get(f"{BASE_URL}/websocket/subscriptions", headers=HEADERS)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Current subscriptions: {data}")
    
    # 2. 새로운 구독 추가
    print("\n2. Adding new subscription...")
    new_topic = "/topic/v1/kr/stock/trade/A000660"  # SK하이닉스
    response = requests.post(
        f"{BASE_URL}/websocket/subscriptions/subscribe",
        params={"topic": new_topic},
        headers=HEADERS
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # 3. 구독 목록 다시 조회
    print("\n3. Getting updated subscriptions...")
    time.sleep(2)  # 잠시 대기
    response = requests.get(f"{BASE_URL}/websocket/subscriptions", headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        print(f"Updated subscriptions: {data}")
    
    # 4. 구독 해제
    print("\n4. Unsubscribing...")
    response = requests.delete(
        f"{BASE_URL}/websocket/subscriptions/unsubscribe",
        params={"topic": new_topic},
        headers=HEADERS
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # 5. 최종 구독 목록 조회
    print("\n5. Final subscriptions...")
    time.sleep(2)  # 잠시 대기
    response = requests.get(f"{BASE_URL}/websocket/subscriptions", headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        print(f"Final subscriptions: {data}")

if __name__ == "__main__":
    test_dynamic_subscription()
