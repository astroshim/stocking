#!/usr/bin/env python3
"""
데이터베이스 관리 스크립트

사용법:
    python db_manager.py create     # 테이블 생성
    python db_manager.py migrate    # 마이그레이션 적용
    python db_manager.py reset      # DB 초기화 (주의!)
    python db_manager.py status     # DB 상태 확인
    python db_manager.py seed       # 샘플 데이터 생성
"""

import os
import sys
import subprocess
from pathlib import Path
from decimal import Decimal

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.config.db import Base, engine, SessionLocal
from app.config import config

# 모든 모델 임포트
from app.db.models import (
    User, Comment, Report, ReportStatusHistory, Notice, Role, UserRole,
    Stock, StockPrice, Order, OrderExecution,
    Portfolio, VirtualBalance, VirtualBalanceHistory,
    Transaction, TradingStatistics, WatchList
)

def run_alembic_command(command: str):
    """Alembic 명령 실행"""
    try:
        result = subprocess.run(['uv', 'run', 'alembic'] + command.split(), 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Alembic 명령 실행 실패: {e}")
        print(f"오류 출력: {e.stderr}")
        return False

def create_tables():
    """테이블 생성 (직접 생성 방식)"""
    print("🚀 데이터베이스 테이블을 직접 생성합니다...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 모든 테이블이 성공적으로 생성되었습니다!")
        return True
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False

def migrate_database():
    """마이그레이션 적용"""
    print("🔄 데이터베이스 마이그레이션을 적용합니다...")
    return run_alembic_command("upgrade head")

def reset_database():
    """데이터베이스 초기화"""
    response = input("⚠️  데이터베이스를 완전히 초기화하시겠습니까? 모든 데이터가 삭제됩니다! (yes/no): ")
    if response.lower() != 'yes':
        print("❌ 작업이 취소되었습니다.")
        return False
    
    try:
        print("🗑️  기존 테이블을 삭제합니다...")
        Base.metadata.drop_all(bind=engine)
        
        print("🚀 새로운 테이블을 생성합니다...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ 데이터베이스가 성공적으로 초기화되었습니다!")
        return True
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        return False

def check_database_status():
    """데이터베이스 상태 확인"""
    print("📊 데이터베이스 상태를 확인합니다...")
    
    try:
        with engine.connect() as conn:
            # 테이블 목록 확인
            if 'sqlite' in config.DATABASE_URI:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
                tables = [row[0] for row in result.fetchall()]
            else:
                result = conn.execute(text("SHOW TABLES;"))
                tables = [row[0] for row in result.fetchall()]
            
            print(f"📋 총 {len(tables)}개의 테이블이 존재합니다:")
            for table in sorted(tables):
                # 각 테이블의 레코드 수 확인
                try:
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.fetchone()[0]
                    print(f"  - {table}: {count}개 레코드")
                except Exception as e:
                    print(f"  - {table}: 레코드 수 확인 불가 ({e})")
            
            print(f"\n📍 데이터베이스 URI: {config.DATABASE_URI}")
            print(f"📁 데이터베이스 파일: {Path(config.DATABASE_URI.replace('sqlite:///', '')).absolute() if 'sqlite' in config.DATABASE_URI else 'N/A'}")
            
    except Exception as e:
        print(f"❌ 데이터베이스 상태 확인 실패: {e}")
        return False
    
    return True

def seed_sample_data():
    """샘플 데이터 생성"""
    print("🌱 샘플 데이터를 생성합니다...")
    
    db = SessionLocal()
    try:
        # 기본 역할 생성
        admin_role = Role(name="admin", description="관리자")
        user_role = Role(name="user", description="일반 사용자")
        db.add(admin_role)
        db.add(user_role)
        db.flush()
        
        # 샘플 사용자 생성
        admin_user = User(
            userid="admin",
            email="admin@stocking.kr",
            nickname="관리자",
            sign_up_from="stocking"
        )
        test_user = User(
            userid="testuser",
            email="test@stocking.kr", 
            nickname="테스트사용자",
            sign_up_from="stocking"
        )
        db.add(admin_user)
        db.add(test_user)
        db.flush()
        
        # 사용자 역할 할당
        admin_user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
        test_user_role = UserRole(user_id=test_user.id, role_id=user_role.id)
        db.add(admin_user_role)
        db.add(test_user_role)
        
        # 샘플 주식 생성
        stocks = [
            Stock(
                code="005930",
                name="삼성전자",
                market="KOSPI",
                sector="IT",
                industry="반도체",
                market_cap=Decimal("400000000000000"),
                listed_shares=5969782550,
                description="대한민국 최대 전자기업"
            ),
            Stock(
                code="000660",
                name="SK하이닉스", 
                market="KOSPI",
                sector="IT",
                industry="반도체",
                market_cap=Decimal("80000000000000"),
                listed_shares=728002365,
                description="메모리 반도체 전문기업"
            ),
            Stock(
                code="035420",
                name="NAVER",
                market="KOSPI", 
                sector="IT",
                industry="인터넷",
                market_cap=Decimal("50000000000000"),
                listed_shares=164192565,
                description="대한민국 최대 포털사이트"
            )
        ]
        
        for stock in stocks:
            db.add(stock)
        db.flush()
        
        # 주식 가격 정보 생성
        stock_prices = [
            StockPrice(stock_id=stocks[0].id, current_price=Decimal("75000"), 
                      open_price=Decimal("74500"), high_price=Decimal("75500"), 
                      low_price=Decimal("74000"), volume=1000000),
            StockPrice(stock_id=stocks[1].id, current_price=Decimal("120000"),
                      open_price=Decimal("119000"), high_price=Decimal("121000"),
                      low_price=Decimal("118500"), volume=500000),
            StockPrice(stock_id=stocks[2].id, current_price=Decimal("200000"),
                      open_price=Decimal("199000"), high_price=Decimal("201000"), 
                      low_price=Decimal("198000"), volume=300000)
        ]
        
        for price in stock_prices:
            db.add(price)
        
        # 테스트 사용자용 가상 잔고 생성
        virtual_balance = VirtualBalance(
            user_id=test_user.id,
            cash_balance=Decimal("1000000"),
            invested_amount=Decimal("0"),
            total_asset_value=Decimal("1000000"),
            available_cash=Decimal("1000000")
        )
        db.add(virtual_balance)
        
        db.commit()
        print("✅ 샘플 데이터가 성공적으로 생성되었습니다!")
        print("\n📋 생성된 샘플 데이터:")
        print("  - 역할: admin, user")
        print("  - 사용자: admin, testuser")
        print("  - 주식: 삼성전자, SK하이닉스, NAVER")
        print("  - 가상잔고: testuser에게 100만원")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return False
    finally:
        db.close()
    
    return True

def main():
    """메인 함수"""
    print("=" * 60)
    print("🗄️  Stocking API - 데이터베이스 관리자")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("사용법: python db_manager.py [create|migrate|reset|status|seed]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        create_tables()
    elif command == "migrate":
        migrate_database()
    elif command == "reset":
        reset_database()
    elif command == "status":
        check_database_status()
    elif command == "seed":
        seed_sample_data()
    else:
        print(f"❌ 알 수 없는 명령어: {command}")
        print("사용 가능한 명령어: create, migrate, reset, status, seed")
        sys.exit(1)

if __name__ == "__main__":
    main()