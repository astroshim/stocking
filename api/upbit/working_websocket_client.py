#!/usr/bin/env python3
"""
Upbit WebSocket 클라이언트 - 원본 버전 (JavaScript 분석 전)
"""

import asyncio
import websockets
import json
from io import BytesIO
import struct
import uuid

class UpbitWebsocketClient:
    def __init__(self):
        self.uri = "wss://crix-ws-first.upbit.com/websocket"

    def create_subscription_request(self, codes):
        """구독 요청 생성"""
        crix_codes = [f"CRIX.UPBIT.{code}" for code in codes]
        
        request = [
            {"ticket": f"upbit_web-4.84.3-{uuid.uuid4()}"},
            {
                "format": "PRTBUF_LIST"  # Protocol Buffer 리스트 형식 (중요!)
            },
            # {
            #     "type": "recentCrix",  # 실시간 시세 데이터
            #     "codes": crix_codes
            # },
            {
                "type": "crixTrade",   # 체결 데이터도 함께 구독
                "codes": crix_codes
            }
        ]
        return json.dumps(request)

    def extract_double_values(self, data):
        """바이너리 데이터에서 double 값들을 추출"""
        doubles = []
        for i in range(0, len(data) - 7, 4):
            try:
                value = struct.unpack('<d', data[i:i+8])[0]
                doubles.append(value)
            except:
                pass
        return doubles

    def parse_upbit_message(self, data):
        """완전한 메시지 데이터에서 의미있는 정보 추출"""
        # 실제 데이터만 사용 (처음 몇 바이트 건너뛰기)
        actual_data = data[4:]  # 처음 4바이트는 길이 헤더
        
        # CRIX 패턴 위치 찾기
        crix_pos = actual_data.find(b"CRIX.UPBIT.KRW-")
        
        if crix_pos == -1:
            return None  # 패턴을 찾을 수 없음
            
        # 종목 코드 추출 (CRIX.UPBIT.KRW-BTC 형태)
        market_code_start = crix_pos
        market_code_end = market_code_start + 18  # "CRIX.UPBIT.KRW-BTC" 길이
        
        if market_code_end > len(actual_data):
            return None
            
        market_code = actual_data[market_code_start:market_code_end].decode('utf-8')
        
        # 나머지 데이터에서 의미있는 숫자 값들 추출  
        remaining_data = actual_data[market_code_end:]
        
        # double 값들 추출 및 의미 부여
        all_values = []
        
        # 모든 double 값 추출 (4바이트씩 이동하면서)
        i = 0
        while i + 8 <= len(remaining_data):
            try:
                value = struct.unpack('<d', remaining_data[i:i+8])[0]
                all_values.append(value)
            except:
                pass
            i += 4
        
        # 합리적인 가격 범위의 값들만 필터링 (비트코인 기준)
        significant_values = [v for v in all_values if 100 <= abs(v) <= 200000000]  # 100원 ~ 2억원
        
        # test_real_parser.py 결과를 바탕으로 정확한 위치 매핑
        if len(all_values) >= 43:  # 충분한 데이터가 있는 경우
            try:
                # 정확한 인덱스 매핑 (메시지 길이별 다른 인덱스)
                if len(all_values) > 76:  # 338바이트 메시지
                    high_price = all_values[2] if len(all_values) > 2 and 100000 <= abs(all_values[2]) <= 200000000 else 0
                else:  # 237바이트 메시지
                    high_price = all_values[7] if len(all_values) > 7 and 100000 <= abs(all_values[7]) <= 200000000 else 0
                
                # 현재가 찾기 (메시지 길이별 다른 인덱스)
                trade_price = 0
                trade_price_index = -1
                
                if len(all_values) > 76:  # 338바이트 메시지
                    trade_price = all_values[30] if len(all_values) > 30 and 100000 <= abs(all_values[30]) <= 200000000 else 0
                    trade_price_index = 30
                else:  # 237바이트 메시지
                    trade_price = all_values[28] if len(all_values) > 28 and 100000 <= abs(all_values[28]) <= 200000000 else 0
                    trade_price_index = 28
                
                # 현재가를 못 찾으면 기존 방식 사용
                if trade_price == 0:
                    trade_price = significant_values[0] if significant_values else high_price
                
                # 저가 찾기 (현재가 기준으로)
                low_price = trade_price
                
                # 정확한 인덱스로 거래량 추출 (메시지 길이별 다른 인덱스)
                if len(all_values) > 76:  # 338바이트 메시지 (76개 값)
                    acc_trade_volume_24h = all_values[39] if len(all_values) > 39 and 0.1 <= abs(all_values[39]) <= 10000 else 0
                else:  # 237바이트 메시지 (51개 값)
                    acc_trade_volume_24h = all_values[41] if len(all_values) > 41 and 0.1 <= abs(all_values[41]) <= 10000 else 0
                
                # 정확한 인덱스로 전일대비 추출 (사용자 확인됨: 인덱스 36)
                change_price = all_values[36] if len(all_values) > 36 else 0
                
                # 거래대금 찾기 (200억~500억 범위에서 탐색)
                trade_amount = 0
                trade_amount_index = -1
                for i in range(15, min(len(all_values), 50)):
                    val = abs(all_values[i])
                    if 200000000000 <= val <= 500000000000:
                        trade_amount = val
                        trade_amount_index = i
                        break
                
                return {
                    'market': market_code,
                    'trade_price': trade_price,
                    'high_price': high_price,
                    'low_price': low_price,
                    'change_price': change_price,
                    'acc_trade_volume_24h': acc_trade_volume_24h,
                    'acc_trade_price_24h': trade_amount,
                    'total_values_count': len(all_values),
                    'trade_price_index': trade_price_index,
                    'trade_amount_index': trade_amount_index,
                    'message_length': len(data)
                }
                
            except Exception as e:
                print(f"인덱스 매핑 오류: {e}")
        
        return None

    async def connect_and_listen(self):
        """WebSocket 연결 및 메시지 수신"""
        print("🚀 Upbit 웹소켓 클라이언트 시작")
        
        async with websockets.connect(self.uri) as websocket:
            # 구독 요청 전송
            subscription = self.create_subscription_request(["KRW-BTC"])
            await websocket.send(subscription)
            print("📡 구독 요청 완료. 실시간 데이터 수신 대기 중...")
            
            message_count = 0
            total_messages = 0
            
            async for message in websocket:
                if isinstance(message, bytes):
                    total_messages += 1
                    
                    # 디버깅: 메시지 전체 정보 출력
                    if total_messages < 5:  # 처음 5개 메시지만
                        print(f"전체 메시지 길이: {len(message)}, 첫 10바이트: {message[:10].hex()}")
                    
                    # 메시지에서 직접 CRIX 패턴을 찾아서 파싱 (여러 코인 지원)
                    if b"CRIX.UPBIT.KRW-" in message:
                        print(f"🎯 CRIX 패턴 발견! 메시지 길이: {len(message)}")
                        
                        # 정상적인 데이터로 확인된 메시지 길이들 처리 (237, 338바이트)
                        if len(message) in [237, 338]:
                            
                            # 처음 2개 메시지의 raw hex 출력
                            if message_count < 2:
                                print(f"\n📋 메시지 {message_count + 1} Raw Hex:")
                                for i in range(0, min(len(message), 200), 16):
                                    chunk = message[i:i+16]
                                    hex_str = ' '.join(f'{b:02x}' for b in chunk)
                                    ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                                    print(f"{i:04x}: {hex_str:<48} {ascii_str}")
                                print()
                            
                            # 메시지 파싱
                            parsed_data = self.parse_upbit_message(message)
                            
                            if parsed_data:
                                # 메시지 길이에 따른 디버깅 출력
                                if len(message) == 237:
                                    print(f"📊 237바이트 메시지 파싱 결과:")
                                elif len(message) == 338:
                                    print(f"📊 338바이트 메시지 파싱 결과:")
                                
                                current_idx = parsed_data.get('trade_price_index', '?')
                                trade_amount_idx = parsed_data.get('trade_amount_index', '?')
                                
                                print(f"💰 {parsed_data['market']} 실시간 데이터:")
                                print(f"    현재가(인덱스 {current_idx}): {parsed_data['trade_price']:,.0f} 원")
                                high_idx = "2 (338바이트)" if len(message) > 300 else "7 (237바이트)"
                                volume_idx = "39 (338바이트)" if len(message) > 300 else "41 (237바이트)"
                                print(f"    고가(인덱스 {high_idx}): {parsed_data['high_price']:,.0f} 원")
                                print(f"    저가: {parsed_data['low_price']:,.0f} 원")
                                print(f"    전일대비(인덱스 36): {parsed_data['change_price']:,.0f} 원")
                                print(f"    거래량(인덱스 {volume_idx}): {parsed_data['acc_trade_volume_24h']:.3f} BTC")
                                print(f"    거래대금(인덱스 {trade_amount_idx}): {parsed_data['acc_trade_price_24h']:,.0f} 원")
                                print(f"    총 값 개수: {parsed_data['total_values_count']}")
                                print("-" * 60)
                                
                                message_count += 1
                                
                                # 처음 3개 메시지만 상세 분석하고 종료
                                if message_count >= 3:
                                    print("✅ 분석 완료! 3개 메시지 분석했습니다.")
                                    return

async def main():
    client = UpbitWebsocketClient()
    await client.connect_and_listen()

if __name__ == "__main__":
    asyncio.run(main())