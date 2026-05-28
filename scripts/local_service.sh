#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="${JM_AI_TMUX_SESSION:-jm-ai-design-8010}"
HOST="${JM_AI_HOST:-127.0.0.1}"
PORT="${JM_AI_PORT:-8010}"
APP_TARGET="${JM_AI_APP:-app.main:create_app}"
LOG_LINES="${JM_AI_LOG_LINES:-80}"
ACTION="${1:-start}"

if [ -n "${JM_AI_PYTHON:-}" ]; then
  PYTHON_BIN="$JM_AI_PYTHON"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [ -x "/tmp/jm-checktool-py311/bin/python" ]; then
  PYTHON_BIN="/tmp/jm-checktool-py311/bin/python"
else
  PYTHON_BIN="python3"
fi

require_tmux() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux is required to manage the local service." >&2
    exit 1
  fi
}

has_session() {
  tmux has-session -t "$SESSION_NAME" >/dev/null 2>&1
}

print_status() {
  if has_session; then
    echo "session: $SESSION_NAME running"
  else
    echo "session: $SESSION_NAME not running"
  fi

  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/tmp/jm-ai-design-port-"$PORT".txt 2>&1; then
    cat /tmp/jm-ai-design-port-"$PORT".txt
  else
    echo "port: $PORT not listening"
  fi
}

health_check() {
  curl -sS -o /tmp/jm-ai-design-"$PORT"-health.html \
    -w "HTTP %{http_code}\n" \
    "http://$HOST:$PORT/"
}

start_service() {
  require_tmux
  if has_session; then
    echo "Already running."
    print_status
    health_check || true
    return
  fi

  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/tmp/jm-ai-design-port-"$PORT".txt 2>&1; then
    echo "Port $PORT is already in use:" >&2
    cat /tmp/jm-ai-design-port-"$PORT".txt >&2
    exit 1
  fi

  if [ ! -x "$PYTHON_BIN" ]; then
    echo "Python runtime not found or not executable: $PYTHON_BIN" >&2
    exit 1
  fi
  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import uvicorn
PY
  then
    echo "Python runtime cannot import uvicorn: $PYTHON_BIN" >&2
    echo "Set JM_AI_PYTHON to a project environment with dependencies installed." >&2
    exit 1
  fi

  local command
  command="PYTHONPATH=. \"$PYTHON_BIN\" -m uvicorn \"$APP_TARGET\" --factory --host \"$HOST\" --port \"$PORT\" --workers 1 --log-level info"
  tmux new-session -d -s "$SESSION_NAME" -c "$ROOT_DIR" "$command"
  sleep 2
  print_status
  health_check || true
}

stop_service() {
  require_tmux
  if has_session; then
    tmux kill-session -t "$SESSION_NAME"
    echo "Stopped $SESSION_NAME."
  else
    echo "Session $SESSION_NAME is not running."
  fi
}

show_logs() {
  require_tmux
  if ! has_session; then
    echo "Session $SESSION_NAME is not running." >&2
    exit 1
  fi
  tmux capture-pane -t "$SESSION_NAME" -p | tail -n "$LOG_LINES"
}

case "$ACTION" in
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  restart)
    stop_service || true
    start_service
    ;;
  status)
    require_tmux
    print_status
    ;;
  health)
    health_check
    ;;
  logs)
    show_logs
    ;;
  *)
    echo "Usage: npm run {start|stop|restart|status|health|logs}" >&2
    exit 2
    ;;
esac
