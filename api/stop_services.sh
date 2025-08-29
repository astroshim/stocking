#!/bin/bash

# 서비스 중지 스크립트
# WebSocket 데몬과 FastAPI 서버를 안전하게 종료

set -e  # 에러 발생시 스크립트 중단

echo "🛑 Stopping Stock Trading Services..."

# 함수: 프로세스 안전 종료
safe_kill() {
    local pid=$1
    local name=$2
    local timeout=${3:-10}  # 기본 10초 타임아웃
    
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  $name (PID: $pid) is not running or already stopped"
        return 0
    fi
    
    echo "🛑 Stopping $name (PID: $pid)..."
    
    # SIGTERM 전송
    kill -TERM "$pid" 2>/dev/null || true
    
    # 프로세스가 종료되기를 기다림
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt $timeout ]; do
        sleep 1
        ((count++))
        echo "⏳ Waiting for $name to stop... ($count/$timeout)"
    done
    
    # 여전히 실행 중이면 SIGKILL 전송
    if kill -0 "$pid" 2>/dev/null; then
        echo "⚡ Force killing $name (PID: $pid)..."
        kill -KILL "$pid" 2>/dev/null || true
        sleep 2
    fi
    
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "✅ $name stopped successfully"
    else
        echo "❌ Failed to stop $name"
        return 1
    fi
}

# 함수: PID 파일에서 프로세스 중지
stop_from_pidfile() {
    local pidfile=$1
    local name=$2
    
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        safe_kill "$pid" "$name"
        rm -f "$pidfile"
        echo "🗑️  Removed PID file: $pidfile"
    else
        echo "⚠️  PID file not found: $pidfile"
        # PID 파일이 없어도 프로세스명으로 찾아서 종료 시도
        local pids=$(pgrep -f "$name" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "🔍 Found running processes for $name: $pids"
            for pid in $pids; do
                safe_kill "$pid" "$name"
            done
        fi
    fi
}

# 메인 종료 로직
main() {
    echo "📋 Checking running services..."
    
    # 1. WebSocket 데몬 중지
    echo ""
    echo "🔌 Stopping WebSocket Daemon..."
    stop_from_pidfile "/tmp/websocket_daemon.pid" "websocket_daemon"
    
    # 2. FastAPI 서버 중지
    echo ""
    echo "🌐 Stopping FastAPI Server..."
    stop_from_pidfile "/tmp/fastapi.pid" "gunicorn\|uvicorn"
    
    # 3. 추가 정리 작업
    echo ""
    echo "🧹 Cleaning up..."
    
    # 남은 Python 프로세스 중 관련된 것들 정리
    local remaining_pids=$(ps aux | grep -E "(websocket_daemon\.py|main:app)" | grep -v grep | awk '{print $2}' || true)
    if [ -n "$remaining_pids" ]; then
        echo "🔍 Found remaining processes: $remaining_pids"
        for pid in $remaining_pids; do
            safe_kill "$pid" "remaining process"
        done
    fi
    
    # PID 파일들 정리
    rm -f /tmp/websocket_daemon.pid /tmp/fastapi.pid
    
    # 4. Redis 상태 확인 (선택적)
    if command -v redis-cli >/dev/null 2>&1; then
        echo ""
        echo "📊 Checking Redis status..."
        if redis-cli ping >/dev/null 2>&1; then
            echo "✅ Redis is still running (not stopped by this script)"
            echo "💡 To stop Redis: redis-cli shutdown"
        else
            echo "⚠️  Redis is not running"
        fi
    fi
    
    echo ""
    echo "✅ All services stopped successfully!"
    echo ""
    echo "🔗 Useful commands:"
    echo "  - Check processes: ps aux | grep -E '(websocket_daemon|gunicorn|uvicorn)'"
    echo "  - Check Redis: redis-cli ping"
    echo "  - Check ports: lsof -i :8000"
}

# 스크립트 실행
main "$@"
