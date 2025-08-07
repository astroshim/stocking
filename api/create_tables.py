#!/usr/bin/env python3
"""
데이터베이스 테이블 생성 스크립트

사용법:
    python create_tables.py
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.config.db import Base, engine
from app.config import config

# 모든 모델 임포트 (테이블 정의를 위해 필요)
from app.db.models import (
    User, Comment, Report, ReportStatusHistory, Notice, Role, UserRole,
    Stock, StockPrice, Order, OrderExecution,
    Portfolio, VirtualBalance, VirtualBalanceHistory,
    Transaction, TradingStatistics, WatchList
)

def create_database_if_not_exists():
    """데이터베이스가 존재하지 않으면 생성"""
    try:
        # MySQL의 경우 데이터베이스 생성
        if 'mysql' in config.DATABASE_URI:
            # 데이터베이스명 추출
            db_name = config.DATABASE_URI.split('/')[-1].split('?')[0]
            
            # 데이터베이스 없이 연결 (서버 연결용)
            server_uri = config.DATABASE_URI.rsplit('/', 1)[0]
            server_engine = create_engine(server_uri)
            
            with server_engine.connect() as conn:
                # 데이터베이스 존재 확인
                result = conn.execute(text(f"SHOW DATABASES LIKE '{db_name}'"))
                if not result.fetchone():
                    # 데이터베이스 생성
                    conn.execute(text(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                    print(f"✅ 데이터베이스 '{db_name}' 생성 완료")
                else:
                    print(f"📝 데이터베이스 '{db_name}' 이미 존재")
                    
        # SQLite의 경우 자동으로 파일 생성됨
        elif 'sqlite' in config.DATABASE_URI:
            print("📝 SQLite 사용 - 파일이 자동으로 생성됩니다")
            
    except Exception as e:
        print(f"⚠️  데이터베이스 생성 중 오류 (무시 가능): {e}")

def create_all_tables():
    """모든 테이블 생성"""
    try:
        print("🚀 데이터베이스 테이블 생성을 시작합니다...")
        print(f"📍 데이터베이스 URI: {config.DATABASE_URI}")
        
        # 데이터베이스 생성 (필요한 경우)
        create_database_if_not_exists()
        
        # 모든 테이블 생성
        Base.metadata.create_all(bind=engine)
        
        print("\n✅ 모든 테이블이 성공적으로 생성되었습니다!")
        
        # 생성된 테이블 목록 출력
        print("\n📋 생성된 테이블 목록:")
        inspector = engine.dialect.get_table_names(engine.connect())
        for table_name in sorted(Base.metadata.tables.keys()):
            print(f"  - {table_name}")
            
    except Exception as e:
        print(f"❌ 테이블 생성 중 오류 발생: {e}")
        sys.exit(1)

def drop_all_tables():
    """모든 테이블 삭제 (주의: 데이터가 모두 삭제됩니다!)"""
    response = input("⚠️  모든 테이블을 삭제하시겠습니까? 데이터가 영구적으로 삭제됩니다! (yes/no): ")
    if response.lower() == 'yes':
        try:
            Base.metadata.drop_all(bind=engine)
            print("✅ 모든 테이블이 삭제되었습니다.")
        except Exception as e:
            print(f"❌ 테이블 삭제 중 오류 발생: {e}")
    else:
        print("❌ 테이블 삭제가 취소되었습니다.")

def main():
    """메인 함수"""
    print("=" * 60)
    print("🗄️  Stocking API - 데이터베이스 테이블 관리")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "drop":
            drop_all_tables()
        elif command == "recreate":
            drop_all_tables()
            create_all_tables()
        else:
            print(f"❌ 알 수 없는 명령어: {command}")
            print("사용 가능한 명령어: drop, recreate")
    else:
        create_all_tables()

if __name__ == "__main__":
    main()