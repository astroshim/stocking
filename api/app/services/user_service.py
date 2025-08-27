import hashlib
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import jwt
import logging

from app.api.schemas.sns_schema import SocialUserInfo
from app.config import config
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.virtual_balance_repository import VirtualBalanceRepository
from app.db.repositories.watchlist_repository import WatchListRepository
from app.utils.transaction_manager import TransactionManager


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
        self.virtual_balance_repository = VirtualBalanceRepository(repository.session)
        self.watchlist_repository = WatchListRepository(repository.session)
        self.optional_params = [
            'user_id',
            'start_date',
            'end_date',
            'sort_by',
            'sort_order',
            'page',
            'per_page']

    def create_user(self, user_data: Dict[str, Any]) -> User:
        """새로운 사용자 생성"""
        with TransactionManager.transaction(self.repository.session):
            user = User(
                userid=user_data['userid'],
                email=user_data['email'],
                phone=user_data.get('phone', ''),
                name=user_data.get('name', ''),
                avatar_url=user_data.get('avatar_url', ''),
                sign_up_from=user_data.get('sign_up_from', 'stocking'),
                uuid=user_data.get('uuid', ''),
                platform=user_data.get('platform', ''),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            user.password = self.__hash_password(user_data['password'])
            self.__generate_token(user, expires_in=86400)

            self.repository.add(user)
            
            # 사용자 생성 후 가상잔고도 함께 생성
            try:
                from decimal import Decimal
                initial_cash = user_data.get('initial_cash', Decimal('1000000'))  # 기본 100만원
                self.virtual_balance_repository.create_user_balance(user.id, initial_cash)
                logging.info(f"Virtual balance created for user {user.id} with initial cash {initial_cash}")
            except Exception as e:
                logging.error(f"Failed to create virtual balance for user {user.id}: {e}")
                # 가상잔고 생성 실패는 사용자 생성을 막지 않음 (선택적)
            
            # 사용자 생성 후 기본 관심종목 디렉토리도 함께 생성
            try:
                self.watchlist_repository.ensure_default_directory(user.id)
                logging.info(f"Default watchlist directory created for user {user.id}")
            except Exception as e:
                logging.error(f"Failed to create default watchlist directory for user {user.id}: {e}")
                # 기본 디렉토리 생성 실패는 사용자 생성을 막지 않음 (선택적)
                
            return user

    def sns_sign_in(self, social_user_info: SocialUserInfo):
        """
        소셜 로그인 사용자 정보를 바탕으로 사용자를 생성하거나 조회합니다.
        여러 소셜 로그인 플랫폼을 지원합니다.

        Args:
            social_user_info: 소셜 플랫폼에서 제공한 사용자 정보 (통합 형식)

        Returns:
            생성되거나 조회된 사용자 정보
        """
        try:
            social_id = social_user_info.id
            social_type = social_user_info.social_type
            composite_social_id = f"{social_type}_{social_id}"

            # 1. 소셜 ID로 사용자 조회
            user = self.repository.get_by_userid(composite_social_id)

            if user:
                # 기존 사용자가 있는 경우 토큰 생성 후 리턴
                return self.__update_user_token(user)

            # 2. 이메일로 사용자 조회
            if social_user_info.email:
                user = self.repository.get_by_email(social_user_info.email)
                if user:
                    # 기존 이메일 사용자에게 소셜 계정 연결
                    return self.__update_user_token(user)

            # 3. 신규 사용자 생성
            return self.__create_social_user(social_user_info, composite_social_id)

        except Exception as e:
            logging.error(f"Error during SNS sign-in: {e}")
            raise

    def __update_user_token(self, user: User) -> User:
        """사용자의 토큰을 갱신합니다."""
        with TransactionManager.transaction(self.repository.session):
            self.__generate_token(user, expires_in=86400)
            return user

    def __create_social_user(self, social_user_info: SocialUserInfo, composite_social_id: str) -> User:
        """소셜 로그인 사용자를 생성합니다."""
        social_id = social_user_info.id
        social_type = social_user_info.social_type

        # 이메일 및 이름 준비
        email = social_user_info.email or f"{composite_social_id}@{social_type.lower()}.user"
        username = social_user_info.name or f"User_{social_type}_{social_id[:8] if len(social_id) > 8 else social_id}"

        with TransactionManager.transaction(self.repository.session):
            user = User(
                userid=composite_social_id,
                email=email,
                name=username,
                avatar_url=social_user_info.profile_image or '',
                sign_up_from=social_type,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # 랜덤 비밀번호 생성
            user.password = self.__hash_password(uuid.uuid4().hex[:16])
            self.__generate_token(user, expires_in=86400)

            self.repository.add(user)
            
            # 소셜 로그인 사용자도 가상잔고 생성
            try:
                from decimal import Decimal
                initial_cash = Decimal('1000000')  # 기본 100만원
                self.virtual_balance_repository.create_user_balance(user.id, initial_cash)
                logging.info(f"Virtual balance created for social user {user.id} with initial cash {initial_cash}")
            except Exception as e:
                logging.error(f"Failed to create virtual balance for social user {user.id}: {e}")
                # 가상잔고 생성 실패는 사용자 생성을 막지 않음
            
            # 소셜 로그인 사용자도 기본 관심종목 디렉토리 생성
            try:
                self.watchlist_repository.ensure_default_directory(user.id)
                logging.info(f"Default watchlist directory created for social user {user.id}")
            except Exception as e:
                logging.error(f"Failed to create default watchlist directory for social user {user.id}: {e}")
                # 기본 디렉토리 생성 실패는 사용자 생성을 막지 않음
                
            return user

    @staticmethod
    def __hash_password(password):
        # 솔트 생성 (실제 사용시에는 사용자별로 유니크한 솔트를 사용해야 합니다)
        salt = os.urandom(32)

        # 비밀번호와 솔트를 합쳐서 해시
        hashed = hashlib.sha256(salt + password.encode()).hexdigest()

        # 솔트와 해시를 함께 저장 (콜론으로 구분self.repository.session)
        return f"{salt.hex()}:{hashed}"

    @staticmethod
    def __check_password(stored_password, provided_password):
        salt, hashed = stored_password.split(':')
        # 저장된 솔트를 사용하여 제공된 비밀번호를 해시
        return hashed == hashlib.sha256(bytes.fromhex(salt) + provided_password.encode()).hexdigest()

    def login(self, login_data: Dict[str, Any], client_ip: str = None) -> Optional[User]:
        with TransactionManager.transaction(self.repository.session):
            logging.debug(f"login_data: {login_data}")

            user = self.get_by_userid(login_data['userid'])
            logging.debug(f"user: {user}")

            # if user and user.check_password(password):
            if user and self.__check_password(user.password, login_data['password']):
                self.__generate_token(user, expires_in=86400)
                user.last_sign_in_at = datetime.now()
                user.last_sign_in_ip = client_ip
                user.sign_in_count = user.sign_in_count + 1
                return user

            raise Exception(f"Invalid userid or password")

    def set_push_token(self, user_id: str, push_token_data: Dict[str, Any]) -> Optional[User]:
        """푸시 토큰 설정"""
        with TransactionManager.transaction(self.repository.session):
            user = self.repository.get_by_id(user_id)
            if user:
                user.push_token = push_token_data['push_token']
                user.platform = push_token_data['platform']
                user.updated_at = datetime.now()
                return user
            return None

    def __generate_token(self, user, expires_in=3600):
        """Generate JWT token with user roles."""
        # 사용자 역할 정보 가져오기
        from app.services.service_factory import role_service_factory
        role_service = role_service_factory(self.repository.session)
        roles = role_service.get_user_roles(user.id)

        # 관리자 여부 확인 (기존 is_admin 필드와의 호환성 유지)
        if user.is_admin and 'admin' not in roles:
            roles.append('admin')

        # 역할이 없는 경우 기본 역할 부여
        if not roles:
            roles.append('user')

        # 토큰 생성
        user.access_token = jwt.encode(
            {
                'sub': str(user.id),
                'exp': datetime.now() + timedelta(seconds=expires_in),
                'roles': roles
            },
            config.JWT_SECRET_KEY,
            algorithm='HS256'
        )

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
        """사용자 정보 업데이트"""
        with TransactionManager.transaction(self.repository.session):
            user = self.repository.get_by_id(user_id)
            if user:
                for key, value in user_data.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                user.updated_at = datetime.now()
            return user

    def delete_user(self, user_id: str) -> bool:
        """사용자 삭제"""
        with TransactionManager.transaction(self.repository.session):
            user = self.repository.get_by_id(user_id)
            if user:
                self.repository.delete(user)
                return True
            return False

    # 조회 메서드는 트랜잭션 불필요
    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.repository.get_by_id(user_id)

    def get_by_userid(self, userid: str) -> Optional[User]:
        return self.repository.get_by_userid(userid)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.repository.get_by_email(email)

    def list_users(self, page: int = 1, per_page: int = 10):
        return self.repository.list_users(page, per_page)
