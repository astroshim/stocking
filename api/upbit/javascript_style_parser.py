#!/usr/bin/env python3
"""
JavaScript 코드 분석을 바탕으로 한 정확한 웹소켓 패킷 파서
"""

import asyncio
import websockets
import json
from io import BytesIO
import struct

class JavaScriptStyleUpbitParser:
    def __init__(self):
        self.uri = "wss://crix-ws-first.upbit.com/websocket"

    def create_subscription_request(self, codes):
        """구독 요청 생성 - JavaScript 코드와 동일"""
        crix_codes = [f"CRIX.UPBIT.{code}" for code in codes]
        
        request = [
            {
                "ticket": "test-ticket-001"
            },
            {
                "type": "recentCrix",
                "codes": crix_codes,
                "format": "PRTBUF_LIST"
            }
        ]
        return json.dumps(request)

    def analyze_packet_structure(self, data):
        """JavaScript 코드 기반 패킷 구조 분석"""
        print(f"\n🔍 === 패킷 구조 상세 분석 ===")
        print(f"📏 총 길이: {len(data)}바이트")
        
        # 1. 첫 10바이트 분석
        if len(data) >= 10:
            header = data[:10]
            print(f"🏷️  첫 10바이트:")
            print(f"   HEX: {header.hex()}")
            print(f"   DEC: {[b for b in header]}")
            
            # big-endian으로 해석한 길이값들
            if len(data) >= 4:
                length_be = int.from_bytes(data[:4], 'big')
                print(f"   Big-endian 길이: {length_be}")
                
        # 2. CRIX 패턴 찾기
        crix_pos = data.find(b"CRIX.UPBIT.KRW-")
        if crix_pos != -1:
            print(f"📍 CRIX 패턴 위치: {crix_pos}")
            
            # CRIX 앞 데이터 분석
            prefix = data[:crix_pos]
            print(f"🔍 CRIX 앞 데이터 ({len(prefix)}바이트):")
            
            for i in range(len(prefix)):
                byte_val = prefix[i]
                print(f"   [{i:2d}]: 0x{byte_val:02x} = {byte_val:3d} = {chr(byte_val) if 32 <= byte_val <= 126 else '?'}")
                
                # Protobuf wire format 해석
                if i > 0 and i < len(prefix) - 1:
                    # field number와 wire type 분석
                    field_num = byte_val >> 3
                    wire_type = byte_val & 0x07
                    if field_num > 0 and field_num < 32 and wire_type < 6:
                        print(f"       -> Protobuf field #{field_num}, wire type {wire_type}")
            
            # CRIX 문자열 확인
            market_start = crix_pos
            market_end = data.find(b'\x10', market_start)  # 다음 field 찾기
            if market_end > market_start:
                market_str = data[market_start:market_end]
                print(f"🏪 마켓 문자열: {market_str.decode('utf-8', errors='ignore')}")
                
                # 다음 필드부터 분석
                self.analyze_protobuf_fields(data[market_end:], market_end)
                
        return crix_pos

    def parse_protobuf_message(self, data):
        """JavaScript 분석 기반 완전한 Protobuf 메시지 파싱"""
        try:
            print(f"\n🔬 JavaScript 기반 Protobuf 파싱: {len(data)}바이트")
            
            pos = 0
            fields = {}
            market_code = None
            
            while pos < len(data) - 1:
                if pos >= len(data):
                    break
                    
                # Field tag 읽기
                tag_byte = data[pos]
                field_num = tag_byte >> 3
                wire_type = tag_byte & 0x07
                
                print(f"  Field {field_num}: wire_type={wire_type} at pos={pos}")
                pos += 1
                
                if wire_type == 0:  # Varint
                    value, consumed = self.read_varint(data, pos)
                    pos += consumed
                    fields[field_num] = value
                    print(f"    -> Varint: {value}")
                    
                elif wire_type == 1:  # 64-bit fixed (double)
                    if pos + 8 <= len(data):
                        value = struct.unpack('<d', data[pos:pos+8])[0]
                        pos += 8
                        fields[field_num] = value
                        print(f"    -> Double: {value}")
                        
                elif wire_type == 2:  # Length-delimited (string/bytes)
                    length, consumed = self.read_varint(data, pos)
                    pos += consumed
                    
                    if pos + length <= len(data):
                        field_data = data[pos:pos+length]
                        pos += length
                        
                        # FrontModelInfo 처리 (field 1)
                        if field_num == 1:
                            crix_pos = field_data.find(b"CRIX.UPBIT.KRW-")
                            if crix_pos != -1:
                                end_pos = field_data.find(b'\x10', crix_pos)
                                if end_pos == -1:
                                    end_pos = len(field_data)
                                market_code = field_data[crix_pos:end_pos].decode('utf-8', errors='ignore')
                                print(f"    -> Market: {market_code}")
                        else:
                            try:
                                str_val = field_data.decode('utf-8', errors='ignore')
                                fields[field_num] = str_val
                                print(f"    -> String: {str_val}")
                            except:
                                fields[field_num] = field_data
                                print(f"    -> Bytes: {len(field_data)} bytes")
                                
                elif wire_type == 5:  # 32-bit fixed (float)
                    if pos + 4 <= len(data):
                        value = struct.unpack('<f', data[pos:pos+4])[0]
                        pos += 4
                        fields[field_num] = value
                        print(f"    -> Float: {value}")
                else:
                    print(f"    -> Unknown wire type: {wire_type}")
                    break
            
            # JavaScript 코드 기반 정확한 필드 매핑
            if market_code and len(fields) >= 5:
                result = {
                    'market': market_code,
                    'trade_price': fields.get(2, 0),           # field 2: tradePrice
                    'opening_price': fields.get(3, 0),         # field 3: openingPrice  
                    'high_price': fields.get(4, 0),            # field 4: highPrice
                    'low_price': fields.get(5, 0),             # field 5: lowPrice
                    'acc_trade_volume': fields.get(6, 0),      # field 6: accTradeVolume
                    'acc_trade_volume_24h': fields.get(7, 0),  # field 7: accTradeVolume24h
                    'acc_trade_price': fields.get(8, 0),       # field 8: accTradePrice
                    'acc_trade_price_24h': fields.get(9, 0),   # field 9: accTradePrice24h
                    'change_rate': fields.get(17, 0),          # field 17: changeRate (float)
                    'change_price': fields.get(18, 0),         # field 18: changePrice
                    'signed_change_rate': fields.get(19, 0),   # field 19: signedChangeRate
                    'signed_change_price': fields.get(20, 0),  # field 20: signedChangePrice
                    'total_fields': len(fields)
                }
                
                print(f"\n🎯 JavaScript 기반 완전한 파싱 결과:")
                print(f"   마켓: {result['market']}")
                print(f"   현재가: {result['trade_price']:,.0f}원")
                print(f"   시가: {result['opening_price']:,.0f}원")
                print(f"   고가: {result['high_price']:,.0f}원") 
                print(f"   저가: {result['low_price']:,.0f}원")
                print(f"   24시간 거래량: {result['acc_trade_volume_24h']:.3f} BTC")
                print(f"   24시간 거래대금: {result['acc_trade_price_24h']:,.0f}원")
                print(f"   전일대비: {result['change_price']:,.0f}원")
                print(f"   변화율: {result['change_rate']:.3f}%")
                print(f"   총 필드 수: {result['total_fields']}")
                
                return result
                
        except Exception as e:
            print(f"❌ Protobuf 파싱 오류: {e}")
            
        return None

    def read_varint(self, data):
        """Varint 값 읽기"""
        value = 0
        shift = 0
        pos = 0
        
        while pos < len(data):
            byte = data[pos]
            value |= (byte & 0x7F) << shift
            pos += 1
            
            if (byte & 0x80) == 0:
                break
                
            shift += 7
            
        return value, pos

    async def connect_and_analyze(self):
        """웹소켓 연결 및 JavaScript 스타일 분석"""
        print("🚀 JavaScript 스타일 Upbit 웹소켓 분석기 시작")
        
        async with websockets.connect(self.uri) as websocket:
            # 구독 요청 전송
            subscription = self.create_subscription_request(["KRW-BTC"])
            await websocket.send(subscription)
            print("📡 구독 요청 완료")
            
            message_count = 0
            buffer = b""
            
            async for raw_data in websocket:
                if isinstance(raw_data, bytes):
                    buffer += raw_data
                    print(f"\n📦 Raw 데이터 수신: +{len(raw_data)}바이트 (총 {len(buffer)}바이트)")
                    
                    # 충분한 데이터가 쌓이면 분석
                    if len(buffer) >= 100:
                        print(f"\n🎯 === 메시지 #{message_count + 1} 분석 ===")
                        
                        # PRTBUF_LIST에서 Protobuf 메시지 찾기
                        protobuf_start = -1
                        for i in range(len(buffer) - 10):
                            if buffer[i] == 0x0A:  # field 1, wire type 2
                                protobuf_start = i
                                break
                        
                        if protobuf_start != -1:
                            print(f"📍 Protobuf 메시지 발견 at {protobuf_start}")
                            
                            # JavaScript 방식으로 파싱
                            parsed_result = self.parse_protobuf_message(buffer[protobuf_start:])
                            
                            if parsed_result:
                                print(f"\n✅ JavaScript 기반 파싱 성공!")
                                print("=" * 60)
                            
                            message_count += 1
                            
                            # 3개 메시지 분석 후 종료
                            if message_count >= 3:
                                print("\n🎉 JavaScript 기반 분석 완료!")
                                return
                            
                            # 분석한 메시지 제거
                            buffer = buffer[200:]
                        else:
                            # Protobuf 시작점을 못 찾으면 패킷 구조 분석
                            crix_pos = self.analyze_packet_structure(buffer)
                            if crix_pos != -1:
                                buffer = buffer[100:]

async def main():
    parser = JavaScriptStyleUpbitParser()
    await parser.connect_and_analyze()

if __name__ == "__main__":
    asyncio.run(main())
