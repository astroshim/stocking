#!/bin/bash

# 서비스 시작 스크립트
# FastAPI + Gunicorn과 WebSocket 데몬을 함께 실행

set -e  # 에러 발생시 스크립트 중단

echo "🚀 Starting Stock Trading Services..."

# 환경 변수 설정 (기본값)
export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_DB=${REDIS_DB:-0}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Redis 연결 테스트
echo "🔄 Testing Redis connection..."
if ! timeout 5 bash -c "echo > /dev/tcp/$REDIS_HOST/$REDIS_PORT" 2>/dev/null; then
    echo "❌ Redis connection failed: $REDIS_HOST:$REDIS_PORT"
    echo "Please make sure Redis is running and accessible"
    exit 1
fi
echo "✅ Redis connection successful"

# 로그 디렉토리 생성
mkdir -p /tmp/logs

# PID 파일 정리
rm -f /tmp/websocket_daemon.pid /tmp/fastapi.pid

# 종료 시그널 핸들러
cleanup() {
    echo "🛑 Shutting down services..."
    
    # WebSocket 데몬 종료
    if [ -f /tmp/websocket_daemon.pid ]; then
        DAEMON_PID=$(cat /tmp/websocket_daemon.pid)
        if kill -0 $DAEMON_PID 2>/dev/null; then
            echo "🛑 Stopping WebSocket Daemon (PID: $DAEMON_PID)..."
            kill -TERM $DAEMON_PID
            wait $DAEMON_PID 2>/dev/null || true
        fi
        rm -f /tmp/websocket_daemon.pid
    fi
    
    # FastAPI 서버 종료
    if [ -f /tmp/fastapi.pid ]; then
        FASTAPI_PID=$(cat /tmp/fastapi.pid)
        if kill -0 $FASTAPI_PID 2>/dev/null; then
            echo "🛑 Stopping FastAPI Server (PID: $FASTAPI_PID)..."
            kill -TERM $FASTAPI_PID
            wait $FASTAPI_PID 2>/dev/null || true
        fi
        rm -f /tmp/fastapi.pid
    fi
    
    echo "✅ All services stopped"
    exit 0
}

# 시그널 트랩 설정
trap cleanup SIGTERM SIGINT

echo "📡 Starting WebSocket Daemon..."
# WebSocket 데몬 백그라운드 실행
python3 websocket_daemon.py &
DAEMON_PID=$!
echo $DAEMON_PID > /tmp/websocket_daemon.pid
echo "✅ WebSocket Daemon started (PID: $DAEMON_PID)"

# 데몬 시작 대기
sleep 3

# 데몬 상태 확인
if ! kill -0 $DAEMON_PID 2>/dev/null; then
    echo "❌ WebSocket Daemon failed to start"
    exit 1
fi

echo "🌐 Starting FastAPI Server..."
# FastAPI 서버 시작
if [ "$ENVIRONMENT" = "production" ]; then
    # 프로덕션: Gunicorn 사용
    gunicorn main:app -c gunicorn.conf.py &
else
    # 개발: Uvicorn 사용
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
fi

FASTAPI_PID=$!
echo $FASTAPI_PID > /tmp/fastapi.pid
echo "✅ FastAPI Server started (PID: $FASTAPI_PID)"

echo "🎉 All services started successfully!"
echo ""
echo "📊 Service Status:"
echo "  - WebSocket Daemon: PID $DAEMON_PID"
echo "  - FastAPI Server: PID $FASTAPI_PID"
echo "  - Redis: $REDIS_HOST:$REDIS_PORT"
echo ""
echo "🔗 Available Endpoints:"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Realtime Data: http://localhost:8000/api/v1/trading/realtime/stocks/all"
echo "  - Daemon Health: http://localhost:8000/api/v1/trading/realtime/daemon/health"
echo ""
echo "Press Ctrl+C to stop all services..."

# 메인 프로세스들이 살아있는 동안 대기
while kill -0 $DAEMON_PID 2>/dev/null && kill -0 $FASTAPI_PID 2>/dev/null; do
    sleep 5
done

echo "❌ One of the services stopped unexpectedly"
cleanup
