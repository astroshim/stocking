import multiprocessing
import logging
import os
import sys

# 로깅 설정
logformat = '%(asctime)s %(levelname)s %(process)d [%(name)s] %(message)s'

loglevel = os.environ.get('LOG_LEVEL', 'debug').upper()
logging.basicConfig(stream=sys.stdout, level=loglevel, format=logformat)

# 바인딩 설정
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "5100")
bind_env = os.getenv("BIND", None)
if bind_env:
    bind = bind_env
else:
    bind = f"{host}:{port}"

# 워커 수 계산
workers_per_core_str = os.getenv("WORKERS_PER_CORE", "1")
max_workers_str = os.getenv("MAX_WORKERS")
web_concurrency_str = os.getenv("WORKERS")  # 기존 WORKERS 환경 변수 지원

cores = multiprocessing.cpu_count()
workers_per_core = float(workers_per_core_str)
default_web_concurrency = workers_per_core * cores

if web_concurrency_str:
    workers = int(web_concurrency_str)
else:
    workers = max(int(default_web_concurrency), 2)
    if max_workers_str:
        workers = min(workers, int(max_workers_str))

print(f"Running with {workers} workers")

# 워커 설정
worker_class = "uvicorn.workers.UvicornWorker"  # FastAPI용 Uvicorn 워커
timeout = int(os.getenv("TIMEOUT", "600"))      # 기존 타임아웃 유지
keepalive = 120                                # 연결 유지 시간

# 디버그 설정
debug = os.getenv("DEBUG", "true").lower() in ('true', '1', 't')

# 접속 로그 설정
accesslog = os.getenv("ACCESS_LOG", "-")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
errorlog = os.getenv("ERROR_LOG", "-")


# 워커 타임아웃
# timeout = 600

# bind = "0.0.0.0:5100"
# workers = os.environ.get('WORKERS', 1)
# debug = True
#
# # 접속 로그를 stdout으로 출력
# accesslog = '-'
# access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
#
# errorlog = '-'

