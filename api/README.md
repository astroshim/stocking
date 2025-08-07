# StocKing API

가상 주식 거래 플랫폼의 백엔드 API 서버입니다.

## 📋 목차

- [시스템 아키텍처](#시스템-아키텍처)
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

## 🗄️ 데이터베이스 관리

자세한 데이터베이스 관리 방법은 [DATABASE.md](DATABASE.md)를 참고하세요.

### 빠른 시작

```bash
# 테이블 생성
python create_tables.py

# 샘플 데이터 생성
python db_manager.py seed

# 데이터베이스 상태 확인
python db_manager.py status
```

## 🛠️ 로컬 개발 환경

### 개발 서버 실행

```bash
# 의존성 설치
uv sync

# 개발 서버 시작
uv run python main.py

# 또는 Gunicorn 사용
WORKER=1 uv run gunicorn main:app
```

### API 문서 확인

개발 서버 실행 후 다음 URL에서 Swagger UI를 확인할 수 있습니다:
- http://localhost:5100/docs

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
PYTHON_ENV=production
DATABASE_URI=mysql+pymysql://stocking:password@host/stocking
JWT_SECRET_KEY=your-secret-key
PORTONE_STORE_ID=your-store-id
PORTONE_V1_API_SECRET=your-api-secret
# ... 기타 환경 변수
```

## 📂 프로젝트 구조

```
app/
├── api/                    # API 엔드포인트
│   ├── schemas/           # 공통 스키마
│   └── v1/               # API v1
│       ├── endpoints/     # 컨트롤러
│       └── schemas/       # v1 스키마
├── config/               # 설정 파일
├── db/                  # 데이터베이스
│   ├── models/          # SQLAlchemy 모델
│   └── repositories/    # 레포지토리 패턴
├── services/            # 비즈니스 로직
├── utils/              # 유틸리티 함수
└── exceptions/         # 커스텀 예외
```

## 🔧 개발 도구

- **Alembic**: 데이터베이스 마이그레이션
- **UV**: Python 패키지 관리
- **Gunicorn**: WSGI 서버
- **Docker**: 컨테이너화
- **pytest**: 테스트 프레임워크
