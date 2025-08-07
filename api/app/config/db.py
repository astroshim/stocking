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

engine = create_engine(
    config.DATABASE_URI,
    echo=False,
    **config.DATABASE_ENGINE_OPTIONS
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
