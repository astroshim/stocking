# 데이터베이스 관리 가이드

## 🗄️ 개요

Stocking API는 SQLAlchemy ORM과 Alembic을 사용하여 데이터베이스를 관리합니다.

- **개발 환경**: SQLite (`app_dev.db`)
- **프로덕션 환경**: MySQL (설정에 따라)
- **마이그레이션 도구**: Alembic

## 📋 테이블 구조

### 👤 사용자 관리
- `users` - 사용자 정보
- `roles` - 역할 정의
- `user_roles` - 사용자-역할 매핑

### 📈 주식 거래
- `stocks` - 주식 정보
- `stock_prices` - 주식 가격 정보
- `orders` - 주문 정보
- `order_executions` - 주문 체결 내역

### 💰 포트폴리오 및 잔고
- `portfolios` - 사용자별 주식 보유 현황
- `virtual_balances` - 가상 거래 잔고
- `virtual_balance_histories` - 잔고 변동 이력

### 📊 거래 및 통계
- `transactions` - 모든 거래 내역
- `trading_statistics` - 거래 통계
- `watch_lists` - 관심 종목

### 💬 커뮤니티
- `comments` - 댓글
- `reports` - 신고
- `report_status_histories` - 신고 처리 이력
- `notices` - 공지사항

## 🚀 데이터베이스 생성 방법

### 방법 1: 간단한 테이블 생성

```bash
# 모든 테이블을 한 번에 생성
python create_tables.py

# 기존 테이블 삭제 후 재생성
python create_tables.py recreate

# 모든 테이블 삭제 (주의!)
python create_tables.py drop
```

### 방법 2: Alembic 마이그레이션 (권장)

```bash
# 1. 초기 마이그레이션 생성 (이미 완료됨)
uv run alembic revision --autogenerate -m "Initial migration"

# 2. 마이그레이션 적용
uv run alembic upgrade head

# 3. 마이그레이션 상태 확인
uv run alembic current
uv run alembic history

# 4. 마이그레이션 롤백
uv run alembic downgrade -1  # 1단계 뒤로
uv run alembic downgrade base  # 처음으로
```

## 🛠️ 데이터베이스 관리 스크립트

### db_manager.py 사용법

```bash
# 테이블 생성
python db_manager.py create

# 마이그레이션 적용
python db_manager.py migrate

# 데이터베이스 초기화 (주의!)
python db_manager.py reset

# 데이터베이스 상태 확인
python db_manager.py status

# 샘플 데이터 생성
python db_manager.py seed
```

## 🔧 개발 환경 설정

### SQLite (개발용)

```python
# app/config/development.py
DATABASE_URI: str = 'sqlite:///./app_dev.db'
DATABASE_ENGINE_OPTIONS: dict = {
    'connect_args': {'check_same_thread': False}
}
```

### MySQL (프로덕션용)

```python
# app/config/production.py
DATABASE_URI: str = 'mysql+pymysql://user:password@localhost/stocking'
DATABASE_ENGINE_OPTIONS: dict = {
    'pool_size': 10,
    'pool_timeout': 60,
    'max_overflow': 128,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'connect_args': {
        'connect_timeout': 60,
        'read_timeout': 60,
        'write_timeout': 120
    }
}
```

## 📊 모델 관계도

```
User (사용자)
├── VirtualBalance (가상잔고) 1:1
├── Orders (주문) 1:N
├── Portfolios (포트폴리오) 1:N
├── Transactions (거래내역) 1:N
├── TradingStatistics (거래통계) 1:N
├── WatchLists (관심종목) 1:N
├── Comments (댓글) 1:N
├── Reports (신고) 1:N
└── UserRoles (역할) N:M

Stock (주식)
├── StockPrices (가격정보) 1:N
├── Orders (주문) 1:N
├── Portfolios (포트폴리오) 1:N
├── Transactions (거래내역) 1:N
└── WatchLists (관심종목) 1:N

Order (주문)
└── OrderExecutions (체결내역) 1:N

VirtualBalance (가상잔고)
└── VirtualBalanceHistories (잔고이력) 1:N
```

## 🔍 데이터베이스 조회

### SQLite CLI 사용

```bash
# SQLite 데이터베이스 접속
sqlite3 app_dev.db

# 테이블 목록 확인
.tables

# 테이블 구조 확인
.schema users

# 데이터 조회
SELECT * FROM users;
SELECT * FROM stocks;
SELECT * FROM virtual_balances;

# 종료
.quit
```

### Python으로 조회

```python
from app.config.db import SessionLocal
from app.db.models import User, Stock, VirtualBalance

db = SessionLocal()

# 사용자 목록
users = db.query(User).all()
print(f"사용자 수: {len(users)}")

# 주식 목록  
stocks = db.query(Stock).all()
print(f"주식 수: {len(stocks)}")

# 가상 잔고 목록
balances = db.query(VirtualBalance).all()
print(f"가상 잔고 수: {len(balances)}")

db.close()
```

## ⚠️ 주의사항

### 데이터 백업

```bash
# SQLite 백업
cp app_dev.db app_dev_backup_$(date +%Y%m%d).db

# MySQL 백업
mysqldump -u username -p stocking > backup_$(date +%Y%m%d).sql
```

### 마이그레이션 주의사항

1. **프로덕션 배포 전 반드시 백업**
2. **마이그레이션 파일 버전 관리 필수**
3. **다운그레이드 경로 미리 계획**
4. **대용량 데이터 마이그레이션 시 단계별 실행**

### 개발 팁

1. **모델 변경 시 자동 마이그레이션 생성**
   ```bash
   uv run alembic revision --autogenerate -m "설명"
   ```

2. **개발 중 빠른 리셋**
   ```bash
   python db_manager.py reset && python db_manager.py seed
   ```

3. **프로덕션과 개발 환경 분리**
   ```bash
   PYTHON_ENV=production python db_manager.py status
   ```

## 🚨 문제 해결

### 일반적인 오류

1. **Connection refused**: 데이터베이스 서버 미실행
2. **Table already exists**: 기존 테이블과 충돌
3. **Foreign key constraint**: 관계 설정 오류
4. **Migration conflict**: 마이그레이션 순서 문제

### 해결 방법

```bash
# 1. 완전 초기화
python db_manager.py reset

# 2. 마이그레이션 히스토리 확인
uv run alembic history --verbose

# 3. 특정 버전으로 이동
uv run alembic upgrade <revision_id>

# 4. 강제 마이그레이션 적용
uv run alembic stamp head
```