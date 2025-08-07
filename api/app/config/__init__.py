import os

# 현재 환경 설정 (기본값은 development)
ENV = os.environ.get('PYTHON_ENV', 'development')

# 환경별 설정 동적 로드
if ENV == 'production':
    from .production import ProductionConfig as EnvironmentConfig
else:
    from .development import DevelopmentConfig as EnvironmentConfig

# 설정 인스턴스 생성
settings = EnvironmentConfig()

# 필수 설정 검증
def validate_config(config):
    """필수 설정 값이 모두 존재하는지 확인"""
    required_settings = [
        'PYTHON_ENV',
        'DATABASE_URI',
        'JWT_SECRET_KEY',
    ]

    missing = [key for key in required_settings if not getattr(config, key)]

    if missing:
        raise ValueError(f"Missing required config settings: {', '.join(missing)}")

validate_config(settings)

# 모듈 레벨 설정 변수 생성
config = settings
