"""
Toss WebSocket Proxy Service
메인 엔트리포인트
"""
import asyncio
import argparse
import json
from typing import Dict, Any

from src.proxy_service import TossProxyService, run_proxy_service
from src.worker_handler import custom_stock_processor, analytics_processor
from src.models import ProxyMessage, MessageType
from src.config import config


def create_custom_processor():
    """사용자 정의 메시지 처리기 생성"""
    def enhanced_processor(message: ProxyMessage) -> None:
        """향상된 메시지 처리기"""
        try:
            print(f"\n{'='*60}")
            print(f"📨 New Message Received")
            print(f"{'='*60}")
            print(f"🏷️  Type: {message.message_type}")
            print(f"📍 Topic: {message.topic}")
            print(f"🆔 Subscription ID: {message.subscription_id}")
            print(f"⏰ Timestamp: {message.timestamp}")
            
            # 데이터 내용 분석
            if message.data:
                headers = message.data.get('headers', {})
                body = message.data.get('body', '')
                
                print(f"📋 Headers:")
                for key, value in headers.items():
                    print(f"   {key}: {value}")
                
                if body:
                    print(f"📄 Body Preview:")
                    # JSON 파싱 시도
                    try:
                        parsed_body = json.loads(body)
                        print(f"   {json.dumps(parsed_body, indent=2, ensure_ascii=False)}")
                    except json.JSONDecodeError:
                        # JSON이 아닌 경우 일부만 출력
                        preview = body[:200] + "..." if len(body) > 200 else body
                        print(f"   {preview}")
            
            print(f"{'='*60}\n")
            
            # 기본 처리기도 실행
            custom_stock_processor(message)
            
        except Exception as e:
            print(f"❌ Enhanced processor error: {e}")
    
    return enhanced_processor


async def interactive_mode():
    """대화형 모드"""
    print("\n🎯 Toss WebSocket Proxy - Interactive Mode")
    print("=" * 50)
    
    # 서비스 생성
    service = TossProxyService(create_custom_processor())
    
    # 서비스 시작
    if not await service.start():
        print("❌ Failed to start service")
        return
    
    try:
        print("\n✅ Service started successfully!")
        print("\n📖 Available commands:")
        print("  sub <symbol> [market]  - Subscribe to stock (e.g., sub A005930 kr)")
        print("  unsub <symbol> [market] - Unsubscribe from stock")
        print("  bulk <symbol1,symbol2,...> [market] - Bulk subscribe")
        print("  status                 - Show service status")
        print("  subs                   - Show active subscriptions")
        print("  health                 - Show health status")
        print("  quit                   - Exit")
        
        while service.is_running:
            try:
                command = input("\n>>> ").strip().split()
                if not command:
                    continue
                
                cmd = command[0].lower()
                
                if cmd == "quit" or cmd == "exit":
                    break
                
                elif cmd == "sub":
                    if len(command) < 2:
                        print("❌ Usage: sub <symbol> [market]")
                        continue
                    
                    symbol = command[1]
                    market = command[2] if len(command) > 2 else "kr"
                    
                    subscription_id = await service.subscribe_to_stock(symbol, market)
                    if subscription_id:
                        print(f"✅ Subscribed to {symbol} ({market}) - ID: {subscription_id}")
                    else:
                        print(f"❌ Failed to subscribe to {symbol}")
                
                elif cmd == "unsub":
                    if len(command) < 2:
                        print("❌ Usage: unsub <symbol> [market]")
                        continue
                    
                    symbol = command[1]
                    market = command[2] if len(command) > 2 else "kr"
                    
                    success = await service.unsubscribe_from_stock(symbol, market)
                    if success:
                        print(f"✅ Unsubscribed from {symbol} ({market})")
                    else:
                        print(f"❌ Failed to unsubscribe from {symbol}")
                
                elif cmd == "bulk":
                    if len(command) < 2:
                        print("❌ Usage: bulk <symbol1,symbol2,...> [market]")
                        continue
                    
                    symbols = command[1].split(',')
                    market = command[2] if len(command) > 2 else "kr"
                    
                    subscription_ids = await service.bulk_subscribe_stocks(symbols, market)
                    print(f"✅ Bulk subscription completed: {len(subscription_ids)}/{len(symbols)} stocks")
                
                elif cmd == "status":
                    status = service.get_service_status()
                    print(f"\n📊 Service Status:")
                    print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
                
                elif cmd == "subs":
                    if service.subscription_manager:
                        active_subs = service.subscription_manager.get_active_subscriptions()
                        print(f"\n📋 Active Subscriptions ({len(active_subs)}):")
                        for sub in active_subs:
                            print(f"  - {sub.topic} (ID: {sub.subscription_id}, Messages: {sub.message_count})")
                    else:
                        print("❌ Subscription manager not available")
                
                elif cmd == "health":
                    if service.health_monitor:
                        health = service.health_monitor.get_health_summary()
                        print(f"\n🏥 Health Status:")
                        print(json.dumps(health, indent=2, ensure_ascii=False, default=str))
                    else:
                        print("❌ Health monitor not available")
                
                else:
                    print(f"❌ Unknown command: {cmd}")
                
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"❌ Command error: {e}")
    
    finally:
        print("\n🛑 Stopping service...")
        await service.stop()
        print("✅ Service stopped")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Toss WebSocket Proxy Service")
    parser.add_argument("--mode", choices=["service", "interactive"], default="interactive",
                      help="Run mode: service (daemon) or interactive")
    parser.add_argument("--symbols", type=str, 
                      help="Comma-separated stock symbols to subscribe (e.g., A005930,A000660)")
    parser.add_argument("--market", choices=["kr", "us"], default="kr",
                      help="Stock market")
    
    args = parser.parse_args()
    
    print("🚀 Toss WebSocket Proxy Service")
    print(f"📍 Mode: {args.mode}")
    print(f"📊 Config: {config.websocket_url}")
    
    if args.mode == "interactive":
        try:
            asyncio.run(interactive_mode())
        except KeyboardInterrupt:
            print("\n🛑 Service interrupted by user")
    
    elif args.mode == "service":
        # 서비스 모드로 실행
        message_processor = create_custom_processor()
        
        # 자동 구독할 심볼이 있다면 처리
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(',')]
            print(f"📈 Auto-subscribing to: {symbols} ({args.market})")
            
            # 서비스에 자동 구독 로직 추가 필요
            # 현재는 기본 구독만 지원
        
        run_proxy_service(message_processor)


if __name__ == "__main__":
    main()
