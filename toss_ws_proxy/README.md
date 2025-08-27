# Toss WebSocket Proxy Service

안정적인 Toss WebSocket 연결과 실시간 주식 데이터 처리를 위한 프록시 서비스입니다.

## 🌟 주요 특징

- **단일 WebSocket 연결**: 하나의 메인 프로세스에서 WebSocket 연결 관리
- **자동 재연결**: 연결 실패 시 자동 재연결 및 복구
- **워커 스레드**: 메시지 처리를 위한 멀티 스레드 아키텍처  
- **동적 구독 관리**: 실시간으로 종목 구독/해제 가능
- **헬스 모니터링**: 서비스 상태 모니터링 및 자동 복구
- **확장 가능**: 사용자 정의 메시지 처리기 지원

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Main Process   │    │   Worker Threads │    │ Health Monitor  │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │ WebSocket   │ │────┤ │ MessageWorker│ │    │ │ Metrics     │ │
│ │ Client      │ │    │ │     #1       │ │    │ │ Collection  │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │Subscription │ │    │ │ MessageWorker│ │    │ │ Auto        │ │
│ │ Manager     │ │    │ │     #2       │ │    │ │ Recovery    │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Message Bridge  │
                    │ (async → thread)│
                    └─────────────────┘
```

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
cd toss_ws_proxy
pip install -e .
```

### 2. 설정 파일 생성

```bash
cp config.env.example .env
# .env 파일을 편집하여 필요한 설정 수정
```

### 3. 실행

#### 대화형 모드 (권장)
```bash
python main.py --mode interactive
```

#### 서비스 모드 
```bash
python main.py --mode service --symbols A005930,A000660 --market kr
```

## 📖 사용법

### 대화형 모드 명령어

```bash
# 주식 구독
>>> sub A005930 kr        # 삼성전자 구독
>>> sub AAPL us          # 애플 구독 (미국)

# 일괄 구독
>>> bulk A005930,A000660,A035420 kr

# 구독 해제  
>>> unsub A005930 kr

# 상태 확인
>>> status               # 전체 서비스 상태
>>> subs                 # 활성 구독 목록
>>> health               # 헬스 상태

# 종료
>>> quit
```

### 프로그래밍 방식 사용

```python
from src.proxy_service import TossProxyService
from src.models import ProxyMessage

# 사용자 정의 메시지 처리기
def my_processor(message: ProxyMessage):
    print(f"Received: {message.topic} - {message.data}")

# 서비스 생성 및 실행
async def main():
    service = TossProxyService(my_processor)
    
    if await service.start():
        # 주식 구독
        await service.subscribe_to_stock("A005930", "kr")
        
        # 서비스 실행
        await service.run()

import asyncio
asyncio.run(main())
```

## 🔧 설정

주요 설정 항목들:

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `WEBSOCKET_URL` | `wss://realtime-socket.tossinvest.com/ws` | WebSocket 서버 URL |
| `MAX_RECONNECT_ATTEMPTS` | `10` | 최대 재연결 시도 횟수 |
| `WORKER_THREAD_COUNT` | `2` | 워커 스레드 개수 |
| `MAX_MESSAGE_QUEUE_SIZE` | `10000` | 메시지 큐 최대 크기 |
| `HEARTBEAT_INTERVAL` | `4.0` | 하트비트 간격 (초) |

## 📊 모니터링

### 헬스 상태

서비스는 다음 항목들을 모니터링합니다:

- **연결 상태**: WebSocket 연결 및 하트비트
- **메시지 처리**: 처리 속도 및 에러율
- **시스템 리소스**: CPU, 메모리 사용량
- **구독 상태**: 활성/실패 구독 수

### 자동 복구

문제 발생 시 자동으로 다음 액션들을 수행합니다:

- WebSocket 재연결
- 메모리 정리 (Garbage Collection)
- 메시지 큐 클리어
- 서비스 재시작 (극단적인 경우)

## 🛠️ 개발

### 사용자 정의 메시지 처리기

```python
from src.models import ProxyMessage, MessageType
import json

def custom_processor(message: ProxyMessage):
    if message.message_type == MessageType.STOCK_TRADE:
        # JSON 데이터 파싱
        body = message.data.get('body', '')
        if body:
            try:
                data = json.loads(body)
                symbol = data.get('symbol')
                price = data.get('price')
                
                # 사용자 로직 구현
                print(f"{symbol}: {price}")
                
                # 데이터베이스 저장
                # save_to_database(symbol, price, data)
                
                # 알림 발송
                # send_notification(symbol, price)
                
            except json.JSONDecodeError:
                pass
```

### 확장 가능한 구조

- `src/worker_handler.py`: 메시지 처리 로직 추가
- `src/subscription_manager.py`: 구독 관리 로직 수정
- `src/health_monitor.py`: 모니터링 메트릭 추가
- `src/config.py`: 설정 항목 추가

## ⚠️ 주의사항

1. **쿠키 관리**: Toss API 인증을 위한 쿠키가 필요합니다
2. **재연결 제한**: 너무 빈번한 재연결은 서버에서 차단될 수 있습니다
3. **메모리 사용량**: 대량의 구독 시 메모리 사용량을 모니터링하세요
4. **네트워크 안정성**: 안정적인 네트워크 환경에서 사용하세요

## 🐛 문제 해결

### 연결 실패
- 쿠키 설정 확인
- 네트워크 연결 상태 확인  
- 방화벽 설정 확인

### 메모리 과다 사용
- `MAX_MESSAGE_QUEUE_SIZE` 설정 조정
- 워커 스레드 수 조정
- 사용하지 않는 구독 해제

### 메시지 손실
- 큐 크기 설정 확인
- 워커 처리 속도 개선
- 에러 로그 확인

## 📝 라이센스

이 프로젝트는 교육 및 개발 목적으로 만들어졌습니다.
