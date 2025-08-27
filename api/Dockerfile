# Multi-stage build로 이미지 크기 최적화
FROM python:3.11-slim AS builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 작업 디렉터리 설정
WORKDIR /app

# 프로젝트 파일 복사 (의존성만)
COPY pyproject.toml uv.lock ./

# 의존성 설치 (가상환경에)
RUN uv sync --frozen --no-dev

# ===== 최종 런타임 이미지 =====
FROM python:3.11-slim

# ARG로 빌드 인자 정의
ARG ENV="production"
ARG LOG_LEVEL="info"

ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY

# 빌드 인자를 환경 변수로 설정
ENV ENV=$ENV
ENV LOG_LEVEL=$LOG_LEVEL
ENV AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
ENV AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
ENV PYTHON_ENV=$ENV

# 시스템 패키지 최신화 및 정리
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉터리 설정
WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# builder에서 가상환경 복사
COPY --from=builder /app/.venv /app/.venv

# 소스 코드만 선별적으로 복사
COPY main.py ./
COPY app/ ./app/
COPY gunicorn.conf.py ./
COPY pyproject.toml uv.lock ./
# COPY .env.${ENV} .env
# .env.production은 런타임에 외부에서 주입 (보안상 권장)

# 컨테이너에서 사용할 포트를 명시적으로 지정
EXPOSE 8000

# 스크립트 실행 권한 부여
RUN chmod +x start_services.sh websocket_daemon.py

# 애플리케이션 실행 (통합 서비스 스크립트 사용)
CMD ["./start_services.sh"]
