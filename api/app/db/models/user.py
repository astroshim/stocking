from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Numeric
from sqlalchemy.orm import relationship

from app.config.db import Base
from app.db.models.uuid_mixin import UUIDMixin


class User(UUIDMixin, Base):
    __tablename__ = 'users'

    userid = Column(String(255), nullable=False, unique=True, comment='유저 고유 아이디')
    email = Column(String(255), nullable=False, default='', unique=True, comment='이메일')
    password = Column(String(255), nullable=False, default='')
    phone = Column(String(255), nullable=True, comment='전화번호')
    name = Column(String(255), nullable=False, default='', comment='user 이름')
    sign_in_count = Column(Integer, nullable=False, default=0)
    last_sign_in_at = Column(DateTime, nullable=True, comment='마지막 로그인 시간')
    last_sign_in_ip = Column(String(255), nullable=True, comment='마지막 로그인 아이피')
    access_token = Column(String(255), nullable=True)
    refresh_token = Column(String(255), nullable=False, default='', comment='refresh token')
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    avatar_url = Column(String(255), nullable=True, default='', comment='프로필 이미지')
    exposure = Column(Integer, nullable=True, default=0, comment='노출여부')
    uuid = Column(String(255), nullable=True, default='', comment='SNS id or random generated uuid')
    sign_up_from = Column(String(255), nullable=True, default='stocking',
                          comment='SNS(kakao, google, naver, facebook) or stocking')
    is_admin = Column(Boolean, nullable=True, default=False, comment='어드민여부')
    push_token = Column(String(255), nullable=True, default='', comment='push token')
    platform = Column(String(255), nullable=True, default='', comment='폰 플랫폼')
    push_on = Column(Boolean, nullable=True, default=True)

    reports = relationship('Report', back_populates='reporter', foreign_keys='Report.user_id',
                           cascade='all, delete-orphan')

    comments = relationship('Comment', back_populates='user',
                            foreign_keys='Comment.user_id', cascade='all, delete-orphan')

    # 사용자의 역할 관계
    roles = relationship('UserRole', back_populates='user', cascade='all, delete-orphan')



    # 사용자가 작성한 공지사항
    notices = relationship('Notice', foreign_keys='Notice.creator_id', back_populates='creator')

    # 주식 거래 관련 관계
    orders = relationship('Order', back_populates='user', cascade='all, delete-orphan')
    portfolios = relationship('Portfolio', back_populates='user', cascade='all, delete-orphan')
    virtual_balance = relationship('VirtualBalance', back_populates='user', uselist=False, cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='user', cascade='all, delete-orphan')
    trading_statistics = relationship('TradingStatistics', back_populates='user', cascade='all, delete-orphan')
    watch_lists = relationship('WatchList', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.userid}>'
