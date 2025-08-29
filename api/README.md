# StocKing API

가상 주식 거래 플랫폼의 백엔드 API 서버입니다.

## 📋 목차

- [시스템 아키텍처](#시스템-아키텍처)
- [실시간 데이터 아키텍처](#실시간-데이터-아키텍처)
- [주문 체결 흐름](#주문-체결-흐름)
- [데이터베이스 관리](#데이터베이스-관리)
- [로컬 개발 환경](#로컬-개발-환경)
- [배포 가이드](#배포-가이드)

## 📊 시스템 아키텍처

### 핵심 기능
- **가상 주식 거래**: 실제 돈 없이 주식 투자 체험
- **포트폴리오 관리**: 보유 종목 추적 및 손익 분석
- **관심 종목**: 사용자별 관심 종목 관리
- **가상 잔고**: 입출금 및 거래 자금 관리
- **실시간 분석**: 거래 통계 및 성과 지표

### 기술 스택
- **Framework**: FastAPI + SQLAlchemy
- **Database**: MySQL / SQLite (개발용)
- **Migration**: Alembic
- **Authentication**: JWT
- **Payment**: PortOne (결제 연동)
- **Realtime Data**: WebSocket + Redis
- **Cache/Message**: Redis (데이터 공유)
- **External API**: Toss Securities (실시간 주가)

## 🔌 실시간 데이터 아키텍처

### 독립 프로세스 구조

본 시스템은 **확장성**과 **안정성**을 위해 실시간 데이터 처리를 별도 프로세스로 분리했습니다.

```mermaid
graph TD
    A["Docker Compose"] --> B["Redis Container"]
    A --> C["API Container"]
    
    C --> D["start_services.sh"]
    D --> E["WebSocket Daemon"]
    D --> F["FastAPI + Gunicorn"]
    
    E --> G["Toss WebSocket"]
    E --> H["Redis 데이터 저장"]
    
    F --> I["API 엔드포인트"]
    I --> J["Redis 데이터 조회"]
    
    K["클라이언트 요청"] --> I
    I --> L["실시간 주가 응답"]
    
    G --> M["실시간 데이터"]
    M --> H
    H --> J
    
    style A fill:#e1f5fe
    style E fill:#c8e6c9
    style F fill:#fff3e0
    style B fill:#ffebee
    style G fill:#f3e5f5
```

### 핵심 컴포넌트

#### 1. **Toss WebSocket Relayer** (`toss_ws_relayer.py`)
- Gunicorn worker와 **완전히 독립된 프로세스**
- Toss Securities WebSocket 연결 관리
- 실시간 주가 데이터 수신 및 Redis 저장
- 자동 재연결 및 헬스체크

#### 2. **Redis 데이터 레이어**
- 실시간 주가 데이터 캐싱 (TTL: 1시간)
- Pub/Sub을 통한 실시간 이벤트 전파
- WebSocket 데몬 상태 모니터링
- Pipeline을 통한 성능 최적화

#### 3. **FastAPI 실시간 API**
- Redis로부터 실시간 데이터 조회
- 여러 종목 일괄 조회 지원
- 데몬 상태 모니터링 API

### 주요 장점

✅ **완전한 프로세스 분리**
- Gunicorn worker 수와 무관하게 WebSocket 연결 1개만 유지
- 각 worker마다 중복 연결 방지로 리소스 효율성 극대화

✅ **확장성**
- FastAPI 서버 스케일링과 독립적으로 실시간 서비스 운영
- 로드밸런서 적용 시에도 데이터 일관성 보장

✅ **안정성**
- 한 서비스 장애가 다른 서비스에 영향 없음
- 자동 재시작 및 시그널 처리를 통한 안전한 종료

✅ **동적 관리**
- 서버 재시작 없이 실시간으로 구독 추가/해제
- Redis Pub/Sub을 통한 안전한 명령 전송
- WebSocket 연결 상태와 무관하게 구독 관리

### 실시간 API 엔드포인트

```bash
# 단일 종목 실시간 조회
GET /api/v1/trading/realtime/stock/{stock_code}

# 여러 종목 일괄 조회
GET /api/v1/trading/realtime/stocks/multiple?stock_codes=A005930&stock_codes=A000660

# 모든 실시간 종목 조회
GET /api/v1/trading/realtime/stocks/all

# WebSocket 데몬 상태 확인
GET /api/v1/trading/realtime/daemon/health
```

### 실행 방법

#### **통합 서비스 실행**
```bash
# Redis + WebSocket 데몬 + FastAPI 한번에 시작
./start_services.sh
```

#### **Docker Compose 실행**
```bash
# 전체 스택 실행 (Redis + API 서비스)
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 동적 구독 관리 시퀀스

WebSocket 데몬의 구독을 실시간으로 추가/해제하는 시퀀스입니다:

```mermaid
sequenceDiagram
    participant Client as "클라이언트"
    participant API as "FastAPI"
    participant Redis as "Redis"
    participant Daemon as "WebSocket Daemon"
    participant Toss as "Toss WebSocket"
    
    Note over Client,Toss: 동적 구독 추가 흐름
    
    Client->>API: POST /websocket/subscriptions/subscribe?topic=A000660
    API->>Redis: PUBLISH commands {"type":"subscribe", "topic":"A000660"}
    
    Daemon->>Redis: LISTEN commands channel
    Redis->>Daemon: Command: subscribe A000660
    Daemon->>Daemon: Process subscribe command
    Daemon->>Toss: STOMP SUBSCRIBE frame
    Toss->>Daemon: RECEIPT/SUCCESS
    
    Daemon->>Redis: SET command_result:id {"success":true}
    API->>Redis: GET command_result:id (polling)
    Redis->>API: Result data
    API->>Client: {"success": true, "message": "Subscribed"}
    
    Note over Daemon,Toss: 실시간 데이터 수신
    Toss->>Daemon: Real-time stock data
    Daemon->>Redis: SETEX stock:realtime:A000660
    
    Note over Client,Toss: 동적 구독 해제 흐름
    
    Client->>API: DELETE /websocket/subscriptions/unsubscribe?topic=A000660
    API->>Redis: PUBLISH commands {"type":"unsubscribe", "topic":"A000660"}
    
    Redis->>Daemon: Command: unsubscribe A000660
    Daemon->>Toss: STOMP UNSUBSCRIBE frame
    Daemon->>Redis: SET command_result:id {"success":true}
    API->>Client: {"success": true, "message": "Unsubscribed"}
```

### 동적 구독 관리 API

```bash
# 새로운 종목 구독 추가
POST /api/v1/admin/websocket/subscriptions/subscribe?topic=/topic/v1/kr/stock/trade/A000660

# 종목 구독 해제
DELETE /api/v1/admin/websocket/subscriptions/unsubscribe?topic=/topic/v1/kr/stock/trade/A000660

# 현재 구독 목록 조회
GET /api/v1/admin/websocket/subscriptions
```

### 🔄 실제 동작 흐름

동적 구독 관리의 전체 프로세스는 다음과 같습니다:

```
1. FastAPI 엔드포인트 → WebSocketCommandService 호출
2. WebSocketCommandService → Redis에 명령 전송  
3. WebSocket 데몬 → Redis에서 명령 수신
4. WebSocket 데몬 → Toss WebSocket에 실제 구독/해제 실행
5. WebSocket 데몬 → Redis에 결과 저장
6. WebSocketCommandService → 폴링으로 결과 조회
7. FastAPI 엔드포인트 → 클라이언트에 응답
```

#### 🎯 **각 단계별 세부 동작**

**1단계**: 클라이언트가 구독 API 호출
- `POST /api/v1/admin/websocket/subscriptions/subscribe?topic=A000660`

**2단계**: Redis Pub/Sub으로 명령 전송
- 채널: `toss_ws_relayer:commands`
- 데이터: `{"type": "subscribe", "topic": "A000660", "command_id": "uuid"}`

**3단계**: 데몬이 명령 수신 및 처리
- `_listen_for_commands()` → `_process_command()` → `_handle_subscribe_command()`

**4단계**: 실제 WebSocket 구독 실행
- STOMP `SUBSCRIBE` 프레임을 Toss로 전송

**5단계**: 결과를 Redis에 저장
- 키: `toss_ws_relayer:command_result:{command_id}`
- 값: `{"success": true, "message": "Successfully subscribed"}`

**6단계**: API가 결과 폴링 (최대 30초)
- 0.5초마다 Redis에서 결과 확인

**7단계**: 클라이언트에 최종 응답
- `{"success": true, "message": "구독 추가 성공"}`

## 🔄 주문 체결 흐름

```mermaid
sequenceDiagram
    participant User as "사용자"
    participant Controller as "OrderController"
    participant OrderService as "OrderService"
    participant OrderRepo as "OrderRepository"
    participant PortfolioRepo as "PortfolioRepository"
    participant BalanceRepo as "VirtualBalanceRepository"
    participant DB as "Database"

    User->>Controller: POST /orders (주문 생성)
    Controller->>OrderService: create_order(user_id, order_data)
    
    Note over OrderService: 주문 유효성 검증
    OrderService->>OrderService: _validate_order()
    
    alt 매수 주문
        OrderService->>BalanceRepo: 잔고 확인 및 예약
        Note over BalanceRepo: available_cash -= 주문금액
    else 매도 주문
        OrderService->>PortfolioRepo: 보유 수량 확인
        Note over PortfolioRepo: current_quantity >= 매도수량
    end
    
    OrderService->>OrderRepo: create_order()
    OrderRepo->>DB: INSERT INTO orders
    
    alt 시장가 주문
        Note over OrderService: 즉시 체결 처리
        OrderService->>OrderService: _execute_market_order()
        OrderService->>OrderRepo: execute_order()
        OrderRepo->>DB: INSERT INTO order_executions
        OrderRepo->>DB: UPDATE orders (status=FILLED)
        
        Note over OrderService: 잔고 업데이트
        OrderService->>OrderService: _update_virtual_balance_for_execution()
        OrderService->>BalanceRepo: 잔고 정산
        BalanceRepo->>DB: UPDATE virtual_balances
        
        Note over OrderService: 포트폴리오 업데이트
        OrderService->>OrderService: _update_portfolio_for_execution()
        alt 매수
            OrderService->>PortfolioRepo: create_portfolio() or update_portfolio_buy()
            PortfolioRepo->>DB: INSERT/UPDATE portfolios
        else 매도
            OrderService->>PortfolioRepo: update_portfolio_sell()
            PortfolioRepo->>DB: UPDATE portfolios
            alt 수량이 0이 되면
                PortfolioRepo->>DB: DELETE FROM portfolios
            end
        end
    else 지정가 주문
        Note over OrderService: 대기 상태로 저장
        Note over OrderService: 실제 시스템에서는 별도 체결 엔진이 처리
    end
    
    OrderService-->>Controller: Order 객체 반환
    Controller-->>User: 주문 생성 완료 응답
```

### 주요 처리 과정

1. **주문 생성**: 사용자가 매수/매도 주문 요청
2. **유효성 검증**: 잔고(매수) 또는 보유수량(매도) 확인
3. **주문 저장**: 데이터베이스에 주문 정보 저장
4. **즉시 체결**: 시장가 주문인 경우 바로 체결 처리
5. **잔고 정산**: 체결 금액에 따른 가상 잔고 업데이트
6. **포트폴리오 반영**: 체결 결과를 포트폴리오에 반영

## 🔄 주문-체결-거래내역 흐름

### Transaction 생성 시점

거래내역(Transaction)은 **실제 체결이 발생했을 때만** 생성됩니다.

```mermaid
graph LR
    A[주문 생성] --> B{시장가?}
    B -->|Yes| C[즉시 체결]
    B -->|No| D[대기 상태]
    C --> E[Transaction 생성]
    D --> F[체결 조건 만족시]
    F --> E
    E --> G[포트폴리오 업데이트]
    G --> H[잔고 업데이트]
```

### ✅ Transaction이 생성되는 경우

1. **매수/매도 주문 체결** - `BUY`/`SELL` 타입
2. **가상 잔고 입금** - `DEPOSIT` 타입  
3. **가상 잔고 출금** - `WITHDRAW` 타입
4. **배당금 수령** - `DIVIDEND` 타입 (향후)
5. **수수료/세금** - `FEE`/`TAX` 타입 (향후)

### ❌ Transaction이 생성되지 않는 경우

1. **주문 생성만** - 아직 체결되지 않음
2. **주문 취소** - 실제 거래가 발생하지 않음
3. **주문 대기** - 지정가 주문 등

### 거래내역 데이터 구조

```python
class Transaction:
    user_id: str          # 사용자 ID
    stock_id: str         # 주식 종목 코드 (주식 거래시)
    order_id: str         # 연결된 주문 ID
    transaction_type: TransactionType  # BUY, SELL, DEPOSIT, WITHDRAW 등
    quantity: int         # 거래 수량
    price: Decimal        # 거래 가격
    amount: Decimal       # 거래 금액
    commission: Decimal   # 수수료
    tax: Decimal          # 세금
    cash_balance_before: Decimal   # 거래 전 잔고
    cash_balance_after: Decimal    # 거래 후 잔고
    transaction_date: DateTime     # 거래 일시
```

## 🗄️ 데이터베이스 관리

자세한 데이터베이스 관리 방법은 [DATABASE.md](DATABASE.md)를 참고하세요.


### 테스트

```
PYTHON_ENV=development DATABASE_URI='sqlite:///:memory:' JWT_SECRET_KEY='dev' uv run pytest -q tests/test_order_flow.py
```

### 빠른 시작

```bash

# ssh 터널후, db migration
DATABASE_URI=mysql\+pymysql:\/\/keauty:aWdj83Kp9dbwlsdktkfkdgodkQkrk6B4N\!\@127.0.0.1/keauty uv run create_tables.py


# 테이블 생성
python create_tables.py

# 샘플 데이터 생성
python db_manager.py seed

# 데이터베이스 상태 확인
python db_manager.py status
```

## 🛠️ 로컬 개발 환경

### 개발 서버 실행

#### **방법 1: 통합 서비스 실행 (권장)**
```bash
# 의존성 설치
uv sync

# Redis 시작 (백그라운드)
redis-server --daemonize yes

# 통합 서비스 시작 (WebSocket 데몬 + FastAPI)
./start_services.sh
```

#### **방법 2: 개별 서비스 실행**
```bash
# Redis 시작
redis-server --daemonize yes

# WebSocket 데몬 시작 (터미널 1)
python3 toss_ws_relayer.py

# FastAPI 서버 시작 (터미널 2)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### **방법 3: Docker Compose 실행**
```bash
# 전체 스택 시작
docker-compose up -d

# 개발 모드로 시작 (로그 확인)
docker-compose up
```

### API 문서 확인

개발 서버 실행 후 다음 URL에서 확인할 수 있습니다:
- **Swagger UI**: http://localhost:8000/docs
- **실시간 데이터**: http://localhost:8000/api/v1/trading/realtime/stocks/all
- **데몬 상태**: http://localhost:8000/api/v1/trading/realtime/daemon/health
- **구독 관리**: http://localhost:8000/api/v1/admin/websocket/subscriptions

### 동적 구독 테스트

```bash
# 동적 구독 기능 테스트
python3 test_dynamic_subscription.py

# 수동 API 테스트
curl -X POST "http://localhost:8000/api/v1/admin/websocket/subscriptions/subscribe?topic=/topic/v1/kr/stock/trade/A000660" \
     -H "Authorization: Bearer YOUR_TOKEN"
```

### MySQL 서버 실행 (선택사항)

```
docker run -d \
  -p 3306:3306 \
  --name mysql \
  --restart always \
  -e TZ=Asia/Seoul \
  -e MYSQL_ROOT_PASSWORD='walnut1234!@#\$' \
  -v /Users/hsshim/walnut_data/mysql:/var/lib/mysql \
  --health-cmd="mysqladmin ping -h localhost" \
  --health-interval=30s \
  --health-timeout=20s \
  --health-retries=10 \
  mysql:8.2.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci
```

### 개발용 SQLite 사용

기본적으로 SQLite를 사용하도록 설정되어 있어 별도 데이터베이스 설정 없이 바로 개발할 수 있습니다.

## 🚀 배포 가이드

### 인프라 배포 순서

1. **Network 인프라 생성**
2. **MySQL RDS 생성**
3. **CloudFormation Stack 생성**
4. **API 서버 배포**
5. **Bastion 호스트 설정** (DB 접근용)

### 데이터베이스 설정

#### 초기 데이터베이스 및 사용자 생성

```sql
# 관리자 계정으로 RDS 접속
mysql -uadmin -p -h dev-mysql-db.ctqke428aiun.ap-northeast-2.rds.amazonaws.com

# 데이터베이스 생성
CREATE DATABASE stocking DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;

# 사용자 생성 및 권한 부여
CREATE USER 'stocking'@'%' IDENTIFIED BY 'LV9Q40QJEnE82LCNGTSL6OK4zgAgduga!';
GRANT ALL PRIVILEGES ON stocking.* TO 'stocking'@'%';
FLUSH PRIVILEGES;
```

#### Bastion 호스트를 통한 접속

```bash
# SSH 터널링
ssh stocking-db-tunnel

# MySQL 접속
mysql -ustocking -h 127.0.0.1 -p -D stocking -P 13306
```

### 환경 변수 설정

프로덕션 배포 시 다음 환경 변수들을 설정해야 합니다:

```bash
# 기본 설정
PYTHON_ENV=production
DATABASE_URI=mysql+pymysql://stocking:password@host/stocking
JWT_SECRET_KEY=your-secret-key

# Redis 설정
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 결제 서비스
PORTONE_STORE_ID=your-store-id
PORTONE_V1_API_SECRET=your-api-secret

# 로그 레벨
LOG_LEVEL=INFO

# Docker/Gunicorn 설정
WORKERS=4
ENVIRONMENT=production
```

## 📂 프로젝트 구조

```
app/
├── api/                    # API 엔드포인트
│   ├── schemas/           # 공통 스키마
│   └── v1/               # API v1
│       ├── endpoints/     # 컨트롤러
│       │   ├── realtime_controller.py      # 실시간 데이터 API
│       │   └── websocket_controller.py     # WebSocket 관리 API
│       └── schemas/       # v1 스키마
│           └── stock_schemas.py            # 주식 데이터 스키마
├── config/               # 설정 파일
├── db/                  # 데이터베이스
│   ├── models/          # SQLAlchemy 모델
│   └── repositories/    # 레포지토리 패턴
├── services/            # 비즈니스 로직
│   ├── redis_service.py              # Redis 클라이언트
│   ├── toss_proxy_service.py         # Toss API 프록시
│   └── toss_websocket_service.py     # WebSocket 서비스
├── utils/              # 유틸리티 함수
└── exceptions/         # 커스텀 예외

# 루트 레벨 파일
toss_ws_relayer.py              # 독립 Toss WebSocket 릴레이어 프로세스
start_services.sh               # 통합 서비스 실행 스크립트
docker-compose.yml              # Docker Compose 설정
test_dynamic_subscription.py    # 동적 구독 테스트 스크립트
```

## 포트원 사용방법

### 사용 방법
  - 결제창 호출 전 서버에서 파라미터 발급:
    - 요청: POST /api/v1/payments/portone/prepare
    ```
    Body: {"amount": 10000, "order_name": "프리미엄 구독", "currency": "KRW"}
    ``` 

    - 응답: 
    ```
    store_id, channel_key, payment_id, order_name, amount, currency
    ```

  - 프론트에서 PortOne.requestPayment(...) 호출 시 위 값을 사용

  - 결제 후(승인되면) 프론트에서 완료 동기화:
    - 요청: 
    ```
    POST /api/v1/payments/portone/complete with {"payment_id":"..."}
    ```

  - 웹훅: 콘솔에 `/api/v1/payments/portone/webhook` 등록
    - 서버는 PORTONE_WEBHOOK_SECRET 환경변수 또는 설정에서 검증

### 환경 변수/설정
PORTONE_STORE_ID, PORTONE_V2_API_SECRET, PORTONE_WEBHOOK_SECRET는 이미 development.py/production.py에 정의. PORTONE_CHANNEL_KEY는 환경변수로 주입 가능(없으면 'channel-key' 기본값).


### 요약
1. 결제창 팝업 요청 → /portone/prepare로 파라미터 발급.
2. 프론트에서 프론트sdk 에서 제공되는 PortOne.requestPayment(...) 로 결제 팝업창 실행.
```js
import PortOne from "@portone/browser-sdk/v2";

async function onPayClick() {
  const res = await fetch("/api/v1/payments/portone/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount: 10000, order_name: "프리미엄 구독", currency: "KRW" }),
  });
  const { data } = await res.json();

  const payment = await PortOne.requestPayment({
    storeId: data.store_id,
    channelKey: data.channel_key,
    paymentId: data.payment_id,
    orderName: data.order_name,
    totalAmount: Number(data.amount),
    currency: data.currency,
    customData: { userId: "..." },
  });

  if (!payment.code) {
    await fetch("/api/v1/payments/portone/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment_id: payment.paymentId }),
    });
  }
}
```
2. 결제창 입력/요청 후 → /portone/complete로 승인 동기화.
3. 실제 결제 완료 웹훅 → /portone/webhook에서 검증/수신.


## 🔧 개발 도구

- **Alembic**: 데이터베이스 마이그레이션
- **UV**: Python 패키지 관리
- **Gunicorn**: WSGI 서버 (프로덕션)
- **Uvicorn**: ASGI 서버 (개발)
- **Docker**: 컨테이너화
- **Redis**: 캐시 및 메시지 브로커
- **WebSockets**: 실시간 통신
- **pytest**: 테스트 프레임워크

## 🚀 배포 파일

### 주요 배포 파일
- `start_services.sh`: 통합 서비스 실행 스크립트
- `docker-compose.yml`: Redis + API 서비스 구성
- `toss_ws_relayer.py`: 독립 Toss WebSocket 릴레이어
- `Dockerfile`: API 서버 컨테이너 이미지
- `gunicorn.conf.py`: Gunicorn 설정

### 서비스 상태 확인
```bash
# 프로세스 확인
ps aux | grep toss_ws_relayer
ps aux | grep gunicorn

# Redis 연결 확인
redis-cli ping

# API 헬스체크
curl http://localhost:8000/api/v1/trading/realtime/daemon/health

# 구독 목록 확인
curl http://localhost:8000/api/v1/admin/websocket/subscriptions

# 동적 구독 테스트
python3 test_dynamic_subscription.py
```
