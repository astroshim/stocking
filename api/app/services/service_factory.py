from sqlalchemy.orm import Session

def payment_service_factory(db: Session = None):
    """PaymentService 인스턴스 생성을 위한 팩토리 함수"""
    from app.services.payment_service import PaymentService
    return PaymentService(db)


def role_service_factory(db: Session = None):
    """RoleService 인스턴스 생성을 위한 팩토리 함수"""
    from app.db.repositories.role_repository import RoleRepository, UserRoleRepository
    from app.services.role_service import RoleService

    role_repository = RoleRepository(db)
    user_role_repository = UserRoleRepository(db)
    return RoleService(role_repository, user_role_repository)


def user_service_factory(db: Session = None):
    from app.db.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    """UserService 인스턴스 생성을 위한 팩토리 함수"""
    repository = UserRepository(db)
    return UserService(repository)


def report_service_factory(db: Session = None):
    from app.db.repositories.report_repository import ReportRepository
    from app.services.report_service import ReportService
    return ReportService(ReportRepository(db))

def comment_service_factory(db: Session = None):
    from app.db.repositories.comment_repository import CommentRepository
    from app.services.comment_service import CommentService
    return CommentService(CommentRepository(db))


def notice_service_factory(db: Session = None):
    from app.db.repositories.notice_repository import NoticeRepository
    from app.services.notice_service import NoticeService
    return NoticeService(NoticeRepository(db))

# def get_s3_service(
#         bucket_name: str = None,
#         storage_domain: str = None,
#         region_name: str = 'ap-northeast-2',
#         environment: str = None
# ) -> S3Service:
#
#     # 인자로 받지 않은 경우 settings에서 가져옴
#     bucket_name = bucket_name or config.STORAGE_BUCKET_NAME
#     storage_domain = storage_domain or config.STORAGE_DOMAIN
#     environment = environment or config.PYTHON_ENV
#
#     return S3Service(
#         bucket_name=bucket_name,
#         storage_domain=storage_domain,
#         region_name=region_name,
#         environment=environment
#     ) 