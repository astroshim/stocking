import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import config

# SQLAlchemy 로거 설정
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.propagate = True

if config.PYTHON_ENV == "development":
    sqlalchemy_logger.setLevel(logging.INFO)
else:
    sqlalchemy_logger.setLevel(logging.WARNING)

# 엔진 옵션을 DB 종류에 따라 조정 (sqlite는 일부 옵션이 호환되지 않음)
engine_options = dict(config.DATABASE_ENGINE_OPTIONS or {})
if str(config.DATABASE_URI).startswith("sqlite"):
    # SQLite 전용 최소 옵션
    engine_options = {
        'connect_args': {
            'check_same_thread': False
        }
    }

engine = create_engine(
    config.DATABASE_URI,
    echo=False,
    **engine_options
)

# 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()

# DB 의존성 함수
def get_db():
    """요청마다 DB 세션을 새로 생성하고 요청이 끝나면 닫음"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
