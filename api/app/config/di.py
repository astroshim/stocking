from fastapi import Depends
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.services.service_factory import (
    user_service_factory,
    role_service_factory,
    report_service_factory,
    comment_service_factory,
    notice_service_factory,
    payment_service_factory
)
from app.db.repositories.routine_marketing_repository import RoutineMarketingRepository
from app.services.routine_marketing_service import RoutineMarketingService
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.services.portfolio_service import PortfolioService
from functools import lru_cache


def get_user_service(db: Session = Depends(get_db)):
    """UserService dependency"""
    return user_service_factory(db)


def get_role_service(db: Session = Depends(get_db)):
    """RoleService dependency"""
    return role_service_factory(db)


def get_report_service(db: Session = Depends(get_db)):
    """ReportService dependency"""
    return report_service_factory(db)


def get_comment_service(db: Session = Depends(get_db)):
    """CommentService dependency"""
    return comment_service_factory(db)


def get_notice_service(db: Session = Depends(get_db)):
    """NoticeService dependency"""
    return notice_service_factory(db)


def get_payment_service(db: Session = Depends(get_db)):
    """PaymentService dependency"""
    return payment_service_factory(db)


def get_routine_marketing_service(db: Session = Depends(get_db)):
    """RoutineMarketingService dependency"""
    repository = RoutineMarketingRepository(db)
    return RoutineMarketingService(repository)


def get_portfolio_service(db: Session = Depends(get_db)):
    """PortfolioService dependency"""
    virtual_balance_repository = VirtualBalanceRepository(db)
    return PortfolioService(virtual_balance_repository) 