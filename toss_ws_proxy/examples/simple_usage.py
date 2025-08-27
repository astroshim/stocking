"""
Simple usage example for Toss WebSocket Proxy
간단한 사용 예시
"""
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.proxy_service import TossProxyService
from src.models import ProxyMessage, MessageType
import json


def my_stock_processor(message: ProxyMessage):
    """사용자 정의 주식 데이터 처리기"""
    try:
        if message.message_type == MessageType.STOCK_TRADE:
            print(f"\n📈 [{message.timestamp.strftime('%H:%M:%S')}] Stock Update:")
            print(f"   Topic: {message.topic}")
            
            # 메시지 바디 파싱 시도
            body = message.data.get('body', '')
            if body:
                try:
                    # JSON 데이터인 경우
                    data = json.loads(body)
                    if isinstance(data, dict):
                        symbol = data.get('symbol', 'Unknown')
                        price = data.get('price', 0)
                        volume = data.get('volume', 0)
                        
                        print(f"   Symbol: {symbol}")
                        print(f"   Price: {price:,}")
                        print(f"   Volume: {volume:,}")
                    else:
                        print(f"   Data: {data}")
                        
                except json.JSONDecodeError:
                    # JSON이 아닌 원시 데이터
                    preview = body[:100] + "..." if len(body) > 100 else body
                    print(f"   Raw Data: {preview}")
            
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Processor error: {e}")


async def main():
    """메인 실행 함수"""
    print("🚀 Starting Simple Toss WebSocket Proxy Example")
    print("=" * 50)
    
    # 프록시 서비스 생성
    service = TossProxyService(my_stock_processor)
    
    try:
        # 서비스 시작
        print("📡 Starting proxy service...")
        if not await service.start():
            print("❌ Failed to start service")
            return
        
        print("✅ Service started successfully!")
        
        # 주식 구독
        stocks_to_subscribe = [
            ("A005930", "kr"),  # 삼성전자
            ("A000660", "kr"),  # SK하이닉스
            ("A035420", "kr"),  # NAVER
        ]
        
        print(f"\n📈 Subscribing to {len(stocks_to_subscribe)} stocks...")
        
        for symbol, market in stocks_to_subscribe:
            subscription_id = await service.subscribe_to_stock(symbol, market)
            if subscription_id:
                print(f"   ✅ {symbol} ({market}) - ID: {subscription_id}")
            else:
                print(f"   ❌ Failed to subscribe to {symbol}")
        
        print(f"\n🎧 Listening for real-time data... (Press Ctrl+C to stop)")
        print("=" * 50)
        
        # 실시간 데이터 수신 (무한 루프)
        while service.is_running:
            await asyncio.sleep(1)
            
            # 5분마다 상태 출력
            if int(asyncio.get_event_loop().time()) % 300 == 0:
                status = service.get_service_status()
                print(f"\n📊 Status Update:")
                print(f"   Messages Received: {status['service']['total_messages_received']}")
                print(f"   Messages Processed: {status['service']['total_messages_processed']}")
                if 'subscriptions' in status:
                    print(f"   Active Subscriptions: {status['subscriptions']['active_subscriptions']}")
                print("-" * 30)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping service...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        # 서비스 정리
        await service.stop()
        print("✅ Service stopped successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
