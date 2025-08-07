import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session

class TransactionManager:
    @staticmethod
    @contextmanager
    def transaction(db: Session):
        """
        트랜잭션 컨텍스트 매니저
        사용 예:
        with TransactionManager.transaction(db):
            # 여러 작업 수행
        """
        try:
            yield
            db.commit()
        except Exception as e:
            db.rollback()
            logging.error(f"Transaction failed: {str(e)}")
            raise
