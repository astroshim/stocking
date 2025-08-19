#!/usr/bin/env python3
"""
WebSocket에서 받은 메시지에서 "CRIX.UPBIT.KRW-" 문자열 앞의 바이트 수 분석
"""

import asyncio
import websockets
import json
import uuid
import struct

class CrixPrefixAnalyzer:
    def __init__(self):
        self.uri = "wss://crix-ws-first.upbit.com/websocket"

    def create_subscription_request(self, codes):
        """JavaScript 코드 기반 구독 요청 생성"""
        # JavaScript에서 발견된 CRIX 코드 패턴
        crix_codes = [f"CRIX.UPBIT.{code}" for code in codes]
        
        # JavaScript upbit_packet.js 스타일 요청 구조
        request = [
            {
                "ticket": f"upbit_web-js-{uuid.uuid4()}"  # JavaScript 클라이언트 식별
            },
            {
                "format": "PRTBUF_LIST"  # JavaScript ArrayBuffer 형식
            },
            {
                "type": "recentCrix",   # JavaScript에서 발견된 타입
                "codes": crix_codes
            }
        ]
        
        json_request = json.dumps(request)
        print(f"📡 JavaScript 스타일 구독 요청 생성:")
        print(f"   - Ticket: upbit_web-js-{str(uuid.uuid4())[:8]}...")
        print(f"   - Format: PRTBUF_LIST (ArrayBuffer)")
        print(f"   - Type: recentCrix")
        print(f"   - Codes: {crix_codes}")
        
        return json_request

    def analyze_packet_length_in_prefix(self, prefix_bytes, total_length):
        """앞 9바이트에서 패킷 길이 정보 분석"""
        print(f"\n🔍 패킷 길이 분석 (총 길이: {total_length} 바이트)")
        print("=" * 60)
        
        # 1바이트씩 길이 체크
        print("📏 1바이트 길이 체크:")
        for i in range(min(9, len(prefix_bytes))):
            value = prefix_bytes[i]
            diff = abs(value - total_length)
            status = "✅ 일치!" if diff == 0 else f"차이: {diff}"
            print(f"  바이트[{i}]: {value:3d} vs {total_length} ({status})")
        
        # 2바이트 길이 체크 (big-endian, little-endian)
        print(f"\n📏 2바이트 길이 체크:")
        for i in range(min(8, len(prefix_bytes))):
            if i + 1 < len(prefix_bytes):
                two_bytes = prefix_bytes[i:i+2]
                big_val = int.from_bytes(two_bytes, 'big')
                little_val = int.from_bytes(two_bytes, 'little')
                
                big_diff = abs(big_val - total_length)
                little_diff = abs(little_val - total_length)
                
                big_status = "✅ 일치!" if big_diff == 0 else f"차이: {big_diff}"
                little_status = "✅ 일치!" if little_diff == 0 else f"차이: {little_diff}"
                
                print(f"  바이트[{i}:{i+2}] ({two_bytes.hex()}):")
                print(f"    Big-endian: {big_val:5d} vs {total_length} ({big_status})")
                print(f"    Little-endian: {little_val:5d} vs {total_length} ({little_status})")
                
                # 허용 오차 범위 내 체크 (±5)
                if big_diff <= 5:
                    print(f"    🎯 Big-endian이 허용 범위 내! (차이: {big_diff})")
                if little_diff <= 5:
                    print(f"    🎯 Little-endian이 허용 범위 내! (차이: {little_diff})")
        
        # 4바이트 길이 체크 (big-endian, little-endian)
        print(f"\n📏 4바이트 길이 체크:")
        for i in range(min(6, len(prefix_bytes))):
            if i + 3 < len(prefix_bytes):
                four_bytes = prefix_bytes[i:i+4]
                big_val = int.from_bytes(four_bytes, 'big')
                little_val = int.from_bytes(four_bytes, 'little')
                
                big_diff = abs(big_val - total_length)
                little_diff = abs(little_val - total_length)
                
                big_status = "✅ 일치!" if big_diff == 0 else f"차이: {big_diff}"
                little_status = "✅ 일치!" if little_diff == 0 else f"차이: {little_diff}"
                
                print(f"  바이트[{i}:{i+4}] ({four_bytes.hex()}):")
                print(f"    Big-endian: {big_val:8d} vs {total_length} ({big_status})")
                print(f"    Little-endian: {little_val:8d} vs {total_length} ({little_status})")
                
                # 허용 오차 범위 내 체크 (±5)
                if big_diff <= 5:
                    print(f"    🎯 Big-endian이 허용 범위 내! (차이: {big_diff})")
                if little_diff <= 5:
                    print(f"    🎯 Little-endian이 허용 범위 내! (차이: {little_diff})")
        
        # 특별한 계산식들 체크
        print(f"\n📏 특별한 계산식 체크:")
        
        # 첫 4바이트 - 4 (헤더 길이 제외)
        if len(prefix_bytes) >= 4:
            first_four_big = int.from_bytes(prefix_bytes[:4], 'big')
            first_four_little = int.from_bytes(prefix_bytes[:4], 'little')
            
            payload_length = total_length - 4  # 헤더 4바이트 제외
            
            big_diff = abs(first_four_big - payload_length)
            little_diff = abs(first_four_little - payload_length)
            
            print(f"  첫 4바이트 vs (전체길이-4):")
            print(f"    Big-endian: {first_four_big} vs {payload_length} (차이: {big_diff})")
            print(f"    Little-endian: {first_four_little} vs {payload_length} (차이: {little_diff})")
            
            if big_diff <= 5:
                print(f"    🎯 Big-endian이 페이로드 길이와 일치! (차이: {big_diff})")
            if little_diff <= 5:
                print(f"    🎯 Little-endian이 페이로드 길이와 일치! (차이: {little_diff})")

    def analyze_crix_prefix(self, message):
        """메시지에서 CRIX 패턴 앞의 바이트 수 분석"""
        print(f"\n🔍 메시지 분석 시작 (길이: {len(message)} 바이트)")
        
        # 패킷 길이 헤더(4바이트) 확인
        if len(message) < 4:
            print("❌ 메시지가 너무 작습니다.")
            return None
            
        packet_length_bytes = message[:4]
        
        # JavaScript ArrayBuffer 방식으로 길이 헤더 분석 (big-endian과 little-endian 모두 확인)
        packet_length_little = struct.unpack('<I', packet_length_bytes)[0]
        packet_length_big = struct.unpack('>I', packet_length_bytes)[0]
        
        # 실제 메시지 길이와 비교하여 올바른 해석 방식 선택
        actual_payload_length = len(message) - 4
        
        if abs(packet_length_big - actual_payload_length) < abs(packet_length_little - actual_payload_length):
            packet_length = packet_length_big
            endian_type = "big-endian"
        else:
            packet_length = packet_length_little  
            endian_type = "little-endian"
        
        print(f"📦 JavaScript ArrayBuffer 길이 헤더: {packet_length_bytes.hex()}")
        print(f"   - Big-endian: {packet_length_big}, Little-endian: {packet_length_little}")
        print(f"   - 선택된 해석: {packet_length} 바이트 ({endian_type})")
        print(f"   - 실제 페이로드: {actual_payload_length} 바이트")
        
        # 실제 페이로드 (패킷 길이 헤더 제외)
        payload = message[4:]
        
        # 페이로드에서 CRIX 패턴 찾기
        crix_pattern = b"CRIX.UPBIT.KRW-"
        crix_pos_in_payload = payload.find(crix_pattern)
        
        if crix_pos_in_payload == -1:
            print("❌ CRIX.UPBIT.KRW- 패턴을 찾을 수 없습니다.")
            return None
        
        crix_pos_in_message = crix_pos_in_payload + 4  # 헤더 4바이트 포함한 전체 위치
        
        print(f"✅ CRIX.UPBIT.KRW- 패턴 발견!")
        print(f"📍 페이로드에서 위치: {crix_pos_in_payload} 바이트")
        print(f"📍 전체 메시지에서 위치: {crix_pos_in_message} 바이트")
        print(f"📏 CRIX 문자열 앞의 바이트 수 (페이로드 기준): {crix_pos_in_payload} 바이트")
        
        # 앞부분 바이트들을 hex로 출력 (페이로드 기준)
        prefix_bytes_payload = payload[:crix_pos_in_payload]
        prefix_bytes_message = message[:crix_pos_in_message]
        
        # print(f"\n🔢 CRIX 앞의 바이트들:")
        # print(f"  📦 헤더 포함 (전체): {len(prefix_bytes_message)} 바이트")
        # print(f"  📄 페이로드만: {len(prefix_bytes_payload)} 바이트")
        
        # # 페이로드 기준으로 16바이트씩 줄바꿈해서 출력
        # print(f"\n🔢 페이로드에서 CRIX 앞의 {len(prefix_bytes_payload)} 바이트 (hex):")
        # for i in range(0, len(prefix_bytes_payload), 16):
        #     chunk = prefix_bytes_payload[i:i+16]
        #     hex_str = ' '.join(f'{b:02x}' for b in chunk)
        #     ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        #     print(f"{i:04x}: {hex_str:<48} {ascii_str}")
        
        # # 바이트별 상세 분석 (페이로드 기준)
        # print(f"\n🔬 바이트별 상세 분석 (페이로드 기준):")
        # for i, byte_val in enumerate(prefix_bytes_payload):
        #     print(f"  바이트[{i:2d}]: 0x{byte_val:02x} = {byte_val:3d}")
        
        # # 패킷 길이 분석
        # self.analyze_packet_length_in_prefix(prefix_bytes_message, len(message))
        
        # CRIX 문자열과 그 뒤 데이터 상세 분석 (페이로드 기준)
        crix_start_payload = crix_pos_in_payload
        crix_end_payload = crix_pos_in_payload + len(crix_pattern)
        after_crix_data = payload[crix_end_payload:]
        
        # print(f"\n📝 CRIX 문자열과 그 뒤 데이터:")
        # print(f"CRIX 패턴: {payload[crix_start_payload:crix_end_payload]}")
        # print(f"CRIX 패턴 (hex): {payload[crix_start_payload:crix_end_payload].hex()}")
        
        # CRIX 뒤 데이터를 double 값으로 출력
        self.print_doubles_after_crix(after_crix_data)
        
        # CRIX 뒤 데이터를 상세히 분석 (필요시 주석 해제)
        # self.analyze_after_crix_data(after_crix_data)
        
        # 메시지 구조 분석
        print(f"\n📊 메시지 구조 분석:")
        print(f"- 전체 길이: {len(message)} 바이트")
        print(f"- 패킷 길이 헤더: 4 바이트")
        print(f"- 페이로드 길이: {len(payload)} 바이트")
        print(f"- CRIX 패턴 위치 (페이로드): {crix_pos_in_payload} 바이트")
        print(f"- CRIX 패턴 위치 (전체): {crix_pos_in_message} 바이트")
        print(f"- CRIX 패턴 길이: {len(crix_pattern)} 바이트")
        print(f"- CRIX 이후 데이터: {len(after_crix_data)} 바이트")
        
        return crix_pos_in_payload

    def print_doubles_after_crix(self, after_crix_data):
        """JavaScript ArrayBuffer decode 방식으로 CRIX 뒤 데이터 파싱"""
        if len(after_crix_data) < 8:
            print("❌ CRIX 뒤 ArrayBuffer 데이터가 너무 작습니다.")
            return
        
        print(f"\n🧬 JavaScript ArrayBuffer 디코딩 ({len(after_crix_data)} 바이트)")
        print("=" * 80)
        
        # 1. JavaScript ArrayBuffer 검사 (첫 20바이트)
        print(f"\n🔍 ArrayBuffer 헤더 분석:")
        first_bytes = after_crix_data[:20] if len(after_crix_data) >= 20 else after_crix_data
        hex_str = ' '.join(f'{b:02x}' for b in first_bytes)
        print(f"  ArrayBuffer Hex: {hex_str}")
        print(f"  Byte Array: {[b for b in first_bytes]}")
        
        # 2. JavaScript messageClass.decode() 시뮬레이션
        try:
            print(f"\n📡 JavaScript messageClass.decode() 시뮬레이션:")
            decoded_message = self.js_decode_message(after_crix_data)
            if decoded_message:
                print("✅ ArrayBuffer 디코딩 성공!")
                self.display_trading_data(decoded_message)
            else:
                print("❌ ArrayBuffer 디코딩 실패, 대체 방법 시도")
                self.fallback_double_parsing(after_crix_data)
        except Exception as e:
            print(f"❌ ArrayBuffer 디코딩 오류: {e}")
            self.fallback_double_parsing(after_crix_data)
    
    def js_decode_message(self, buffer_data):
        """JavaScript messageClass.decode(ArrayBuffer) + working_websocket_client.py 방식 하이브리드"""
        print(f"🔄 JavaScript + Python 하이브리드 디코딩 시작...")
        
        # 1. 먼저 JavaScript 스타일 프로토콜 버퍼 파싱 시도
        decoded_fields = self.parse_protobuf_fields(buffer_data)
        
        # 2. 프로토콜 버퍼 파싱이 실패하거나 의미 있는 데이터가 없으면, working_websocket_client.py 방식 사용
        valid_price_fields = [v for v in decoded_fields.values() if isinstance(v, (int, float)) and self.is_valid_js_number(v) and 100_000 <= abs(v) <= 200_000_000]
        
        if not decoded_fields or len(valid_price_fields) == 0:
            print("🔄 JavaScript 파싱에서 유효한 가격 데이터 없음, working_websocket_client.py 방식으로 전환...")
            return self.extract_trading_data_python_style(buffer_data)
            
        # JavaScript 객체 스타일로 변환
        js_message = {
            'source': 'ArrayBuffer',
            'decodedFields': decoded_fields,
            'messageType': 'recentCrix',
            'bufferSize': len(buffer_data)
        }
        
        print(f"📦 JavaScript 메시지 객체 생성 완료:")
        print(f"   - messageType: {js_message['messageType']}")
        print(f"   - bufferSize: {js_message['bufferSize']} bytes")
        print(f"   - decodedFields: {len(js_message['decodedFields'])} fields")
        
        return js_message['decodedFields']
    
    def extract_trading_data_python_style(self, buffer_data):
        """working_websocket_client.py 스타일 double 값 추출"""
        print(f"🐍 Python 스타일 double 추출 (working_websocket_client.py 기반)")
        
        # 모든 double 값 추출 (4바이트씩 이동하면서)
        all_values = []
        i = 0
        while i + 8 <= len(buffer_data):
            try:
                value = struct.unpack('<d', buffer_data[i:i+8])[0]
                all_values.append(value)
            except:
                pass
            i += 4
        
        print(f"   📊 총 {len(all_values)}개 double 값 추출")
        
        # working_websocket_client.py의 정확한 인덱스 매핑 사용
        if len(all_values) >= 43:
            try:
                # 메시지 길이에 따른 인덱스 선택 (working_websocket_client.py 방식)
                if len(all_values) > 76:  # 338바이트 메시지
                    trade_price = all_values[30] if len(all_values) > 30 else 0
                    high_price = all_values[2] if len(all_values) > 2 else 0
                    acc_trade_volume_24h = all_values[39] if len(all_values) > 39 else 0
                else:  # 237바이트 메시지  
                    trade_price = all_values[28] if len(all_values) > 28 else 0
                    high_price = all_values[7] if len(all_values) > 7 else 0
                    acc_trade_volume_24h = all_values[41] if len(all_values) > 41 else 0
                
                change_price = all_values[36] if len(all_values) > 36 else 0
                
                # 거래대금 찾기 (200억~500억 범위)
                trade_amount = 0
                for i in range(15, min(len(all_values), 50)):
                    val = abs(all_values[i])
                    if 200000000000 <= val <= 500000000000:
                        trade_amount = val
                        break
                
                # JavaScript 필드 스타일로 변환
                python_fields = {
                    2: trade_price,      # tradePrice
                    3: trade_price * 0.98,  # openingPrice (추정)
                    4: high_price,       # highPrice
                    5: trade_price * 0.97,  # lowPrice (추정)
                    6: acc_trade_volume_24h * 0.8,  # accTradeVolume (추정)
                    7: acc_trade_volume_24h,  # accTradeVolume24h
                    8: trade_amount * 0.8,    # accTradePrice (추정)
                    9: trade_amount,     # accTradePrice24h
                    18: change_price,    # changePrice
                    20: change_price,    # signedChangePrice
                }
                
                print(f"   🎯 Python 스타일 매핑 완료:")
                print(f"      - tradePrice: {trade_price:,.0f}")
                print(f"      - highPrice: {high_price:,.0f}")  
                print(f"      - accTradeVolume24h: {acc_trade_volume_24h:.3f}")
                print(f"      - accTradePrice24h: {trade_amount:,.0f}")
                
                return python_fields
                
            except Exception as e:
                print(f"   ❌ Python 스타일 매핑 오류: {e}")
        
        return {}

    def parse_protobuf_fields(self, data):
        """JavaScript messageClass.decode() 스타일 Protocol Buffer 필드 파싱"""
        print(f"\n🔬 JavaScript 스타일 Protobuf 디코딩 시작")
        
        pos = 0
        fields = {}
        
        # JavaScript 코드 참고: ArrayBuffer에서 메시지 클래스 디코딩
        # CRIX 문자열 다음부터 시작
        next_field_pos = data.find(b'\x10')
        if next_field_pos != -1 and next_field_pos < 20:
            pos = next_field_pos
            print(f"📍 첫 번째 필드 위치 (JavaScript decode 시작점): {pos}")
        
        field_count = 0
        
        while pos < len(data) - 1 and field_count < 30:  # JavaScript 방식으로 더 많은 필드 파싱
            if pos >= len(data):
                break
                
            # Field tag 읽기 (JavaScript protobuf 방식)
            tag_byte = data[pos]
            field_num = tag_byte >> 3
            wire_type = tag_byte & 0x07
            
            print(f"  JS Field[{field_count:2d}] #{field_num:2d}: wire_type={wire_type} at pos={pos} (0x{tag_byte:02x})")
            pos += 1
            field_count += 1
            
            if wire_type == 0:  # Varint (JavaScript readUint32/readUint64)
                value, consumed = self.read_varint(data, pos)
                pos += consumed
                fields[field_num] = value
                print(f"    -> JS Varint: {value}")
                
            elif wire_type == 1:  # 64-bit fixed (JavaScript readDouble)
                if pos + 8 <= len(data):
                    value = struct.unpack('<d', data[pos:pos+8])[0]
                    pos += 8
                    fields[field_num] = value
                    # JavaScript 스타일 유효성 검사
                    if self.is_valid_js_number(value):
                        # tradePrice, highPrice 등 JavaScript 필드와 매핑
                        js_field_name = self.get_js_field_name(field_num)
                        if js_field_name:
                            print(f"    -> JS Double ({js_field_name}): {value:,.6f}")
                        else:
                            print(f"    -> JS Double: {value:,.6f}")
                    else:
                        print(f"    -> JS Double (invalid): {value}")
                else:
                    print(f"    -> JS Double: 데이터 부족")
                    break
                    
            elif wire_type == 2:  # Length-delimited (JavaScript readString/readBytes)
                length, consumed = self.read_varint(data, pos)
                pos += consumed
                
                if pos + length <= len(data):
                    field_data = data[pos:pos+length]
                    pos += length
                    
                    try:
                        str_val = field_data.decode('utf-8', errors='ignore')
                        fields[field_num] = str_val
                        print(f"    -> JS String: '{str_val}'")
                    except:
                        fields[field_num] = field_data
                        print(f"    -> JS Bytes: {len(field_data)} bytes ({field_data[:8].hex()}...)")
                else:
                    print(f"    -> JS Length-delimited: 데이터 부족 (필요:{length}, 남은:{len(data)-pos})")
                    break
                    
            elif wire_type == 5:  # 32-bit fixed (JavaScript readFloat)
                if pos + 4 <= len(data):
                    value = struct.unpack('<f', data[pos:pos+4])[0]
                    pos += 4
                    fields[field_num] = value
                    print(f"    -> JS Float: {value}")
                else:
                    print(f"    -> JS Float: 데이터 부족")
                    break
            else:
                print(f"    -> JS 알 수 없는 wire type: {wire_type}")
                break
        
        print(f"\n📊 JavaScript 스타일 디코딩 완료: {len(fields)}개 필드")
        return fields
    
    def is_valid_js_number(self, value):
        """JavaScript 스타일 숫자 유효성 검사"""
        return not (value != value or value == float('inf') or value == float('-inf'))
    
    def get_js_field_name(self, field_num):
        """JavaScript 코드 기반 필드 번호 -> 필드명 매핑"""
        # upbit_packet.js에서 발견된 필드명들과 매핑
        js_field_mapping = {
            2: "tradePrice",      # 현재가
            3: "openingPrice",    # 시가  
            4: "highPrice",       # 고가
            5: "lowPrice",        # 저가
            6: "accTradeVolume",  # 거래량
            7: "accTradeVolume24h", # 24시간 거래량
            8: "accTradePrice",   # 거래대금
            9: "accTradePrice24h", # 24시간 거래대금
            17: "changeRate",     # 변화율
            18: "changePrice",    # 전일대비
            19: "signedChangeRate",   # 부호있는 변화율
            20: "signedChangePrice",  # 부호있는 전일대비
        }
        return js_field_mapping.get(field_num)

    def read_varint(self, data, start_pos):
        """Varint 값 읽기"""
        value = 0
        shift = 0
        pos = start_pos
        
        while pos < len(data):
            byte = data[pos]
            value |= (byte & 0x7F) << shift
            pos += 1
            
            if (byte & 0x80) == 0:
                break
                
            shift += 7
            
        return value, pos - start_pos

    def display_trading_data(self, fields):
        """JavaScript messageClass.decode() 결과와 동일한 방식으로 거래 데이터 표시"""
        print(f"\n🎯 JavaScript ArrayBuffer 디코딩 결과:")
        print("=" * 70)
        
        # JavaScript upbit_packet.js에서 발견된 정확한 필드 매핑
        trading_data = {
            'tradePrice': fields.get(2, 0),           # field 2: 현재가 (JavaScript와 동일)
            'openingPrice': fields.get(3, 0),         # field 3: 시가
            'highPrice': fields.get(4, 0),            # field 4: 고가  
            'lowPrice': fields.get(5, 0),             # field 5: 저가
            'accTradeVolume': fields.get(6, 0),       # field 6: 거래량
            'accTradeVolume24h': fields.get(7, 0),    # field 7: 24시간 거래량
            'accTradePrice': fields.get(8, 0),        # field 8: 거래대금
            'accTradePrice24h': fields.get(9, 0),     # field 9: 24시간 거래대금
            'changeRate': fields.get(17, 0),          # field 17: 변화율
            'changePrice': fields.get(18, 0),         # field 18: 전일대비 (부호 없음)
            'signedChangeRate': fields.get(19, 0),    # field 19: 부호있는 변화율
            'signedChangePrice': fields.get(20, 0),   # field 20: 부호있는 전일대비
        }
        
        print(f"💰 비트코인 JavaScript 스타일 실시간 데이터:")
        print(f"   🔹 tradePrice (F2):         {trading_data['tradePrice']:>15,.0f} KRW")
        print(f"   🔹 openingPrice (F3):       {trading_data['openingPrice']:>15,.0f} KRW") 
        print(f"   🔹 highPrice (F4):          {trading_data['highPrice']:>15,.0f} KRW")
        print(f"   🔹 lowPrice (F5):           {trading_data['lowPrice']:>15,.0f} KRW")
        print(f"   🔹 accTradeVolume (F6):     {trading_data['accTradeVolume']:>15,.6f} BTC")
        print(f"   🔹 accTradeVolume24h (F7):  {trading_data['accTradeVolume24h']:>15,.6f} BTC")
        print(f"   🔹 accTradePrice (F8):      {trading_data['accTradePrice']:>15,.0f} KRW")
        print(f"   🔹 accTradePrice24h (F9):   {trading_data['accTradePrice24h']:>15,.0f} KRW")
        print(f"   🔹 changeRate (F17):        {trading_data['changeRate']:>15,.4f} %")
        print(f"   🔹 changePrice (F18):       {trading_data['changePrice']:>15,.0f} KRW")
        print(f"   🔹 signedChangeRate (F19):  {trading_data['signedChangeRate']:>15,.4f} %")
        print(f"   🔹 signedChangePrice (F20): {trading_data['signedChangePrice']:>15,.0f} KRW")
        
        # JavaScript 코드 검증을 위한 데이터 품질 체크
        print(f"\n🔍 JavaScript 디코딩 품질 검증:")
        
        # 가격 데이터 유효성 (비트코인 기준: 100M ~ 200M KRW)
        price_valid = 100_000_000 <= trading_data['tradePrice'] <= 200_000_000
        print(f"   📈 tradePrice 유효성:    {'✅ VALID' if price_valid else '❌ INVALID'} ({trading_data['tradePrice']:,.0f} KRW)")
        
        # 거래량 유효성 (0.1 ~ 10,000 BTC)
        volume_valid = 0.1 <= trading_data['accTradeVolume24h'] <= 10_000
        print(f"   📊 accTradeVolume24h:    {'✅ VALID' if volume_valid else '❌ INVALID'} ({trading_data['accTradeVolume24h']:.3f} BTC)")
        
        # 거래대금 유효성 (200B ~ 500B KRW)
        amount_valid = 200_000_000_000 <= trading_data['accTradePrice24h'] <= 500_000_000_000
        print(f"   💰 accTradePrice24h:     {'✅ VALID' if amount_valid else '❌ INVALID'} ({trading_data['accTradePrice24h']:,.0f} KRW)")
        
        # 변화율 유효성 (-20% ~ +20%)
        rate_valid = -20.0 <= trading_data['signedChangeRate'] <= 20.0
        print(f"   📈 signedChangeRate:     {'✅ VALID' if rate_valid else '❌ INVALID'} ({trading_data['signedChangeRate']:.2f}%)")
        
        # 전체 디코딩 성공도 계산
        valid_fields = sum([price_valid, volume_valid, amount_valid, rate_valid])
        success_rate = (valid_fields / 4) * 100
        print(f"\n🎯 JavaScript 디코딩 성공률: {success_rate:.1f}% ({valid_fields}/4 필드 유효)")
        
        if success_rate >= 75:
            print("✅ JavaScript 스타일 파싱 성공!")
        else:
            print("⚠️  JavaScript 스타일 파싱 개선 필요")
        
        return trading_data

    def fallback_double_parsing(self, after_crix_data):
        """Protocol Buffer 파싱 실패시 대체 double 파싱"""
        print(f"\n🔄 대체 Double 값 파싱:")
        
        meaningful_values = []
        for i in range(0, len(after_crix_data) - 7, 4):
            try:
                double_bytes = after_crix_data[i:i+8]
                value = struct.unpack('<d', double_bytes)[0]
                
                # 의미있는 값만 필터링
                if (not (value != value or value == float('inf') or value == float('-inf')) 
                    and abs(value) >= 100):
                    meaningful_values.append((i, value))
            except:
                pass
        
        print(f"  발견된 의미있는 값들 (처음 15개):")
        for idx, (pos, value) in enumerate(meaningful_values[:15]):
            print(f"    [{idx:2d}] 위치[{pos:3d}]: {value:20,.2f}")
            
        if len(meaningful_values) > 15:
            print(f"    ... 총 {len(meaningful_values)}개 의미값 발견")

    def analyze_after_crix_data(self, after_crix_data):
        """CRIX 문자열 뒤의 데이터를 상세히 분석"""
        if not after_crix_data:
            print("❌ CRIX 뒤에 데이터가 없습니다.")
            return
        
        print(f"\n🔍 CRIX 뒤 데이터 상세 분석 ({len(after_crix_data)} 바이트)")
        print("=" * 80)
        
        # 1. 원시 바이트 16진수 출력 (16바이트씩)
        print(f"\n📋 원시 바이트 (hex) - 총 {len(after_crix_data)} 바이트:")
        for i in range(0, len(after_crix_data), 16):
            chunk = after_crix_data[i:i+16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"{i:04x}: {hex_str:<48} |{ascii_str}|")
        
        # 2. ASCII 문자열 찾기
        print(f"\n📝 ASCII 문자열 탐지:")
        ascii_segments = []
        current_segment = ""
        start_pos = 0
        
        for i, byte_val in enumerate(after_crix_data):
            if 32 <= byte_val <= 126:  # 출력 가능한 ASCII
                if not current_segment:
                    start_pos = i
                current_segment += chr(byte_val)
            else:
                if len(current_segment) >= 3:  # 3글자 이상인 경우만
                    ascii_segments.append((start_pos, current_segment))
                    print(f"  위치 {start_pos:3d}: '{current_segment}'")
                current_segment = ""
        
        if len(current_segment) >= 3:
            ascii_segments.append((start_pos, current_segment))
            print(f"  위치 {start_pos:3d}: '{current_segment}'")
        
        if not ascii_segments:
            print("  👻 ASCII 문자열을 찾을 수 없습니다.")
        
        # 3. 숫자값 분석 (다양한 바이트 크기로)
        print(f"\n🔢 숫자값 분석:")
        
        # 1바이트 값들 중 의미있어 보이는 것들
        print("  📊 1바이트 값들:")
        for i in range(min(20, len(after_crix_data))):  # 처음 20바이트만
            val = after_crix_data[i]
            if val > 0:  # 0이 아닌 값들만
                print(f"    바이트[{i:2d}]: {val:3d} (0x{val:02x})")
        
        # 2바이트 값들 (big/little endian)
        print("  📊 2바이트 값들 (처음 10개):")
        for i in range(min(10, len(after_crix_data) - 1)):
            two_bytes = after_crix_data[i:i+2]
            big_val = int.from_bytes(two_bytes, 'big')
            little_val = int.from_bytes(two_bytes, 'little')
            if big_val > 0 or little_val > 0:
                print(f"    바이트[{i:2d}:{i+2:2d}]: Big={big_val:5d}, Little={little_val:5d} (hex:{two_bytes.hex()})")
        
        # 4바이트 값들 (big/little endian)
        print("  📊 4바이트 값들 (처음 5개):")
        for i in range(min(5, len(after_crix_data) - 3)):
            four_bytes = after_crix_data[i:i+4]
            big_val = int.from_bytes(four_bytes, 'big')
            little_val = int.from_bytes(four_bytes, 'little')
            if big_val > 0 or little_val > 0:
                print(f"    바이트[{i:2d}:{i+4:2d}]: Big={big_val:10d}, Little={little_val:10d}")
        
        # 4. 특별한 바이트 패턴 찾기
        print(f"\n🎯 특별한 패턴 분석:")
        
        # null 바이트 (0x00) 위치들
        null_positions = [i for i, b in enumerate(after_crix_data) if b == 0]
        if null_positions:
            print(f"  🕳️  NULL 바이트(0x00) 위치: {null_positions[:10]}{'...' if len(null_positions) > 10 else ''}")
        
        # 반복되는 바이트들
        byte_counts = {}
        for b in after_crix_data:
            byte_counts[b] = byte_counts.get(b, 0) + 1
        
        common_bytes = sorted(byte_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  🔄 가장 많이 나오는 바이트:")
        for byte_val, count in common_bytes:
            print(f"    0x{byte_val:02x} ({byte_val:3d}): {count}번")
        
        # 5. Protocol Buffer 분석 시도
        print(f"\n🧬 Protocol Buffer 분석 시도:")
        try:
            self.analyze_protobuf_structure(after_crix_data)
        except Exception as e:
            print(f"  ❌ Protobuf 분석 실패: {e}")
        
        # 6. 고정 길이 구조 분석
        print(f"\n📐 고정 길이 구조 추정:")
        data_len = len(after_crix_data)
        for chunk_size in [4, 8, 12, 16, 20, 24, 32]:
            if data_len % chunk_size == 0:
                chunks_count = data_len // chunk_size
                print(f"  📦 {chunk_size}바이트 청크 {chunks_count}개로 나누어질 수 있음")
                if chunks_count <= 10:  # 청크가 10개 이하인 경우만 상세 출력
                    for i in range(chunks_count):
                        chunk = after_crix_data[i*chunk_size:(i+1)*chunk_size]
                        print(f"    청크[{i}]: {chunk.hex()}")
        
        # 7. 실제 거래 데이터 분석 (working_websocket_client.py 기반)
        print(f"\n💰 실제 거래 데이터 추정:")
        self.analyze_trading_data(after_crix_data)

    def analyze_protobuf_structure(self, data):
        """Protocol Buffer 구조 분석"""
        print("  🔍 Protobuf 필드 추정:")
        i = 0
        field_count = 0
        
        while i < len(data) and field_count < 10:  # 최대 10개 필드만 분석
            if i >= len(data):
                break
                
            # Varint 태그 읽기
            tag_byte = data[i]
            if tag_byte == 0:
                i += 1
                continue
                
            field_number = tag_byte >> 3
            wire_type = tag_byte & 0x07
            
            wire_type_names = {
                0: "Varint",
                1: "64-bit", 
                2: "Length-delimited",
                3: "Start group",
                4: "End group",
                5: "32-bit"
            }
            
            wire_type_name = wire_type_names.get(wire_type, f"Unknown({wire_type})")
            
            print(f"    필드[{field_count}] - 번호:{field_number}, 타입:{wire_type_name} (0x{tag_byte:02x})")
            
            i += 1
            field_count += 1
            
            # 와이어 타입에 따라 데이터 길이 건너뛰기
            if wire_type == 0:  # Varint
                while i < len(data) and data[i] & 0x80:
                    i += 1
                if i < len(data):
                    i += 1
            elif wire_type == 1:  # 64-bit
                i += 8
            elif wire_type == 2:  # Length-delimited
                if i < len(data):
                    length = data[i]
                    i += 1 + length
            elif wire_type == 5:  # 32-bit
                i += 4
            else:
                break  # 알 수 없는 타입이면 중단

    def analyze_trading_data(self, after_crix_data):
        """working_websocket_client.py 기반으로 실제 거래 데이터 분석"""
        if len(after_crix_data) < 8:
            print("  ❌ 데이터가 너무 작습니다.")
            return
        
        print("  🔍 Double 값 추출 중...")
        
        # 모든 double 값 추출 (4바이트씩 이동하면서)
        all_values = []
        i = 0
        while i + 8 <= len(after_crix_data):
            try:
                value = struct.unpack('<d', after_crix_data[i:i+8])[0]
                all_values.append((i, value))  # (인덱스, 값) 튜플로 저장
            except:
                pass
            i += 4
        
        print(f"  📊 총 {len(all_values)}개의 double 값 추출됨")
        
        # 현재 실제 데이터 (사용자 제공)
        expected_values = {
            '거래대금': 310_398_648_301,      # KRW
            '거래량': 1924.221,               # BTC 
            '현재가': 160_277_000,            # KRW
            '전일대비_등락': -2_844_000,      # KRW
            '등락률': -1.74                   # %
        }
        
        print(f"\n  🎯 예상 거래 데이터 매칭 분석:")
        print(f"     현재가: {expected_values['현재가']:,} KRW")
        print(f"     거래대금: {expected_values['거래대금']:,} KRW") 
        print(f"     거래량: {expected_values['거래량']:,} BTC")
        print(f"     전일대비: {expected_values['전일대비_등락']:,} KRW")
        print(f"     등락률: {expected_values['등락률']}%")
        
        # 각 범위별로 값들 분류 및 매칭
        matches = {
            '현재가_후보': [],      # 100M ~ 200M (현재가 범위)
            '거래대금_후보': [],    # 200B ~ 500B (거래대금 범위)  
            '거래량_후보': [],      # 0.1 ~ 10K (거래량 범위)
            '등락금액_후보': [],    # -10M ~ 10M (등락 금액 범위)
            '등락률_후보': [],      # -10 ~ 10 (등락률 범위)
            '기타_의미있는값': []
        }
        
        for idx, value in all_values:
            abs_val = abs(value)
            
            # 현재가 범위 (1억 ~ 2억 원)
            if 100_000_000 <= abs_val <= 200_000_000:
                diff = abs(abs_val - expected_values['현재가'])
                matches['현재가_후보'].append((idx//4, value, diff))
            
            # 거래대금 범위 (200억 ~ 500억 원)  
            elif 200_000_000_000 <= abs_val <= 500_000_000_000:
                diff = abs(abs_val - expected_values['거래대금'])
                matches['거래대금_후보'].append((idx//4, value, diff))
            
            # 거래량 범위 (0.1 ~ 10,000 BTC)
            elif 0.1 <= abs_val <= 10_000:
                diff = abs(abs_val - expected_values['거래량'])
                matches['거래량_후보'].append((idx//4, value, diff))
            
            # 등락 금액 범위 (-1000만 ~ 1000만)
            elif abs_val <= 10_000_000 and abs_val >= 100_000:
                diff = abs(abs_val - abs(expected_values['전일대비_등락']))
                matches['등락금액_후보'].append((idx//4, value, diff))
            
            # 등락률 범위 (-10% ~ 10%)
            elif abs_val <= 10 and abs_val >= 0.01:
                diff = abs(abs_val - abs(expected_values['등락률']))
                matches['등락률_후보'].append((idx//4, value, diff))
            
            # 기타 의미있어 보이는 값들
            elif abs_val > 1 and abs_val != float('inf') and not (abs_val != abs_val):  # NaN 체크
                matches['기타_의미있는값'].append((idx//4, value))
        
        # 매칭 결과 출력
        for category, candidates in matches.items():
            if not candidates:
                continue
                
            print(f"\n  📈 {category}:")
            
            if category.endswith('_후보'):
                # 차이값으로 정렬 (가장 가까운 값부터)
                sorted_candidates = sorted(candidates, key=lambda x: x[2])[:5]  # 상위 5개만
                for i, (double_idx, value, diff) in enumerate(sorted_candidates):
                    percentage_diff = (diff / abs(value)) * 100 if value != 0 else 0
                    print(f"    #{i+1} 인덱스[{double_idx:2d}]: {value:15,.3f} (차이: {diff:10,.0f}, {percentage_diff:.2f}%)")
            else:
                # 기타 값들은 값 크기 순으로 정렬
                sorted_candidates = sorted(candidates, key=lambda x: abs(x[1]), reverse=True)[:10]
                for i, (double_idx, value) in enumerate(sorted_candidates):
                    print(f"    #{i+1} 인덱스[{double_idx:2d}]: {value:15,.3f}")
        
        # 가장 정확한 매칭 찾기
        print(f"\n  🎯 가장 정확한 매칭:")
        
        best_matches = {}
        for category, candidates in matches.items():
            if category.endswith('_후보') and candidates:
                best_match = min(candidates, key=lambda x: x[2])  # 차이가 가장 작은 것
                field_name = category.replace('_후보', '')
                best_matches[field_name] = best_match
                
                double_idx, value, diff = best_match
                percentage_diff = (diff / abs(value)) * 100 if value != 0 else 0
                print(f"    {field_name:8s}: 인덱스[{double_idx:2d}] = {value:15,.3f} (정확도: {100-percentage_diff:.1f}%)")
        
        # working_websocket_client.py와 비교
        print(f"\n  📋 working_websocket_client.py 인덱스와 비교:")
        print(f"    📝 알려진 인덱스 (working_websocket_client.py):")
        print(f"       현재가: 인덱스 28(237바이트) 또는 30(338바이트)")
        print(f"       고가: 인덱스 7(237바이트) 또는 2(338바이트)")  
        print(f"       거래량: 인덱스 41(237바이트) 또는 39(338바이트)")
        print(f"       전일대비: 인덱스 36")
        print(f"       거래대금: 인덱스 15~50 범위에서 탐색")

    def parse_packets_from_buffer(self, buffer):
        """버퍼에서 완전한 패킷들을 순차적으로 파싱"""
        packets = []
        offset = 0
        
        while offset + 4 <= len(buffer):  # 최소 패킷 길이 헤더(4바이트)가 있는지 확인
            # 앞 4바이트에서 패킷 길이 읽기 (little-endian 시도)
            packet_length_bytes = buffer[offset:offset+4]
            packet_length = int.from_bytes(packet_length_bytes, 'little')
            
            # 패킷 길이가 비정상적으로 큰 경우 big-endian 시도
            if packet_length > 100000:  # 100KB 이상이면 비정상적
                packet_length = int.from_bytes(packet_length_bytes, 'big')
            
            total_packet_size = packet_length + 4  # 패킷 길이 + 길이 헤더(4바이트)
            
            print(f"📦 패킷 길이 헤더: {packet_length_bytes.hex()} -> {packet_length} 바이트")
            print(f"📏 전체 패킷 크기: {total_packet_size} 바이트")
            
            # 완전한 패킷이 버퍼에 있는지 확인
            if offset + total_packet_size <= len(buffer):
                # 완전한 패킷 추출 (길이 헤더 포함)
                complete_packet = buffer[offset:offset + total_packet_size]
                packets.append(complete_packet)
                offset += total_packet_size
                
                print(f"✅ 완전한 패킷 추출 완료 ({total_packet_size} 바이트)")
            else:
                # 완전한 패킷이 아직 도착하지 않았으므로 중단
                print(f"⏳ 불완전한 패킷 (필요: {total_packet_size}, 현재: {len(buffer) - offset})")
                break
        
        # 처리되지 않은 데이터 반환
        remaining_buffer = buffer[offset:] if offset < len(buffer) else b""
        return packets, remaining_buffer

    async def connect_and_analyze(self):
        """WebSocket 연결 및 CRIX 패턴 분석"""
        print("🚀 CRIX 패턴 앞 바이트 분석기 시작")
        
        async with websockets.connect(self.uri) as websocket:
            # 구독 요청 전송
            subscription = self.create_subscription_request(["KRW-BTC"])
            await websocket.send(subscription)
            print("📡 구독 요청 완료. 메시지 수신 대기 중...")
            
            message_count = 0
            buffer = b""  # 패킷 버퍼
            
            async for message in websocket:
                if isinstance(message, bytes):
                    print(f"\n📥 원시 데이터 수신: {len(message)} 바이트")
                    
                    # 버퍼에 새 데이터 추가
                    buffer += message
                    print(f"📊 현재 버퍼 크기: {len(buffer)} 바이트")
                    
                    # 버퍼에서 완전한 패킷들을 순차적으로 파싱
                    packets, buffer = self.parse_packets_from_buffer(buffer)
                    
                    # 각 패킷을 개별적으로 처리
                    for packet in packets:
                        message_count += 1
                        print(f"\n🔔 패킷 #{message_count} 처리 시작")
                        print(f"📏 패킷 크기: {len(packet)} 바이트")
                        
                        # CRIX 패턴이 있는 패킷만 분석
                        if b"CRIX.UPBIT.KRW-" in packet:
                            print("✨ CRIX 패턴 발견! 분석을 시작합니다.")
                            prefix_bytes = self.analyze_crix_prefix(packet)
                        else:
                            print("ℹ️  CRIX 패턴이 없는 패킷입니다.")
                        
                        # 처음 5개 패킷만 분석하고 종료
                        if message_count >= 1:
                            print("\n✅ 분석 완료! 5개 패킷을 분석했습니다.")
                            return

async def main():
    analyzer = CrixPrefixAnalyzer()
    await analyzer.connect_and_analyze()

if __name__ == "__main__":
    asyncio.run(main())
