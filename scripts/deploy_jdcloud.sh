#!/usr/bin/env bash
set -euo pipefail

# Reusable deployment script for the JDCloud single-port server.
#
# Defaults are intentionally concrete so the command is repeatable:
#   server: root@xy1-gcs.jdcloud.com:20151
#   app port: 7860
#   remote app dir: /opt/jm-ai-design-app_jd
#
# The SSH password is not stored here. Use interactive password entry,
# ~/.ssh/config, or an SSH key.

SSH_USER="${SSH_USER:-root}"
SSH_HOST="${SSH_HOST:-xy1-gcs.jdcloud.com}"
SSH_PORT="${SSH_PORT:-20151}"
APP_PORT="${APP_PORT:-7860}"
REMOTE_APP="${REMOTE_APP:-/opt/jm-ai-design-app_jd}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_NAME="jm-ai-design-app_jd"
ACTION="${1:-deploy}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${SSH_USER}@${SSH_HOST}"
SSH_OPTS=(-p "$SSH_PORT" -o StrictHostKeyChecking=accept-new)
SCP_OPTS=(-P "$SSH_PORT" -o StrictHostKeyChecking=accept-new)
RUNTIME_PACKAGES=(
  'fastapi>=0.115'
  'uvicorn[standard]>=0.30'
  'jinja2>=3.1'
  'python-multipart>=0.0.9'
  'pillow>=10.0'
  'openai>=1.0'
  'python-dotenv>=1.0'
  'argon2-cffi>=23.1'
  'itsdangerous>=2.2'
)

usage() {
  cat <<USAGE
Usage:
  scripts/deploy_jdcloud.sh [deploy|status|logs|stop|start|restart|health]

Defaults:
  SSH_USER=$SSH_USER
  SSH_HOST=$SSH_HOST
  SSH_PORT=$SSH_PORT
  REMOTE_APP=$REMOTE_APP
  APP_PORT=$APP_PORT

Override with environment variables, for example:
  SSH_HOST=example.com APP_PORT=7860 scripts/deploy_jdcloud.sh deploy

Notes:
  - .env is packaged from the local project if it exists.
  - local data/, .venv/, git metadata, and caches are excluded.
  - remote data is persisted under \$REMOTE_APP/shared/data.
USAGE
}

ssh_remote() {
  ssh "${SSH_OPTS[@]}" "$REMOTE" "$@"
}

make_archive() {
  local archive="$1"
  (
    cd "$ROOT_DIR"
    LC_ALL=C COPYFILE_DISABLE=1 tar \
      --format=ustar \
      --exclude=.git \
      --exclude=.venv \
      --exclude='.venv.bak-*' \
      --exclude=data \
      --exclude=data-dev \
      --exclude=outpu \
      --exclude=__pycache__ \
      --exclude='*/__pycache__' \
      --exclude=.pytest_cache \
      --exclude=.mypy_cache \
      --exclude=.ruff_cache \
      --exclude='*.pyc' \
      --exclude='.DS_Store' \
      -czf "$archive" .
  )
}

deploy() {
  local stamp archive remote_archive remote_requirements packages_payload
  stamp="$(date +%Y%m%d-%H%M%S)"
  archive="/tmp/${APP_NAME}-${stamp}.tgz"
  remote_archive="/tmp/${APP_NAME}-${stamp}.tgz"
  remote_requirements="/tmp/${APP_NAME}-${stamp}-requirements.txt"
  packages_payload="$(printf '%s\n' "${RUNTIME_PACKAGES[@]}")"

  echo "Packaging $ROOT_DIR"
  make_archive "$archive"
  echo "Uploading $archive to $REMOTE:$remote_archive"
  scp "${SCP_OPTS[@]}" "$archive" "$REMOTE:$remote_archive"
  echo "Uploading runtime requirements to $REMOTE:$remote_requirements"
  ssh "${SSH_OPTS[@]}" "$REMOTE" "cat > '$remote_requirements'" <<<"$packages_payload"

  echo "Deploying on $REMOTE"
  ssh "${SSH_OPTS[@]}" "$REMOTE" \
    "APP_NAME='$APP_NAME' REMOTE_APP='$REMOTE_APP' APP_PORT='$APP_PORT' PYTHON_BIN='$PYTHON_BIN' REMOTE_ARCHIVE='$remote_archive' REMOTE_REQUIREMENTS='$remote_requirements' RELEASE_STAMP='$stamp' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

APP_NAME="${APP_NAME:?APP_NAME is required}"
APP="${REMOTE_APP:?REMOTE_APP is required}"
APP_PORT="${APP_PORT:?APP_PORT is required}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ARCHIVE="${REMOTE_ARCHIVE:?REMOTE_ARCHIVE is required}"
REQUIREMENTS="${REMOTE_REQUIREMENTS:?REMOTE_REQUIREMENTS is required}"
RELEASE="$APP/releases/${RELEASE_STAMP:?RELEASE_STAMP is required}"

mkdir -p "$APP/releases" "$APP/shared/data"
rm -rf "$RELEASE"
mkdir -p "$RELEASE"
tar -xzf "$ARCHIVE" -C "$RELEASE"

if [ -f "$RELEASE/.env" ]; then
  cp "$RELEASE/.env" "$APP/shared/.env"
fi
if [ ! -f "$APP/shared/.env" ]; then
  echo "Missing .env. Add one locally before deploy, or create $APP/shared/.env on the server." >&2
  exit 1
fi

rm -rf "$RELEASE/data" "$RELEASE/.env"
ln -sfn "$APP/shared/data" "$RELEASE/data"
ln -sfn "$APP/shared/.env" "$RELEASE/.env"

if [ ! -d "$APP/venv" ]; then
  if ! "$PYTHON_BIN" -m venv "$APP/venv"; then
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y python3.10-venv
      "$PYTHON_BIN" -m venv "$APP/venv"
    else
      echo "Failed to create venv and apt-get is not available." >&2
      exit 1
    fi
  fi
fi

"$APP/venv/bin/python" -m pip install --upgrade pip
"$APP/venv/bin/python" -m pip install -r "$REQUIREMENTS"

ln -sfn "$RELEASE" "$APP/current"

cat > "$APP/start.sh" <<START_SCRIPT
#!/usr/bin/env bash
set -euo pipefail
cd "$APP/current"
exec "$APP/venv/bin/python" -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port "$APP_PORT" --workers 1
START_SCRIPT

cat > "$APP/stop.sh" <<'STOP_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP/app.pid"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID"
    for _ in $(seq 1 20); do
      if ! kill -0 "$PID" >/dev/null 2>&1; then
        break
      fi
      sleep 0.5
    done
  fi
  rm -f "$PID_FILE"
fi
STOP_SCRIPT

cat > "$APP/status.sh" <<STATUS_SCRIPT
#!/usr/bin/env bash
set -euo pipefail
APP="$APP"
APP_PORT="$APP_PORT"
printf 'current: '
readlink -f "\$APP/current" || true
if [ -f "\$APP/app.pid" ]; then
  PID="\$(cat "\$APP/app.pid")"
  if kill -0 "\$PID" >/dev/null 2>&1; then
    echo "pid: \$PID running"
  else
    echo "pid: \$PID not running"
  fi
else
  echo "pid: none"
fi
lsof -nP -iTCP:"\$APP_PORT" -sTCP:LISTEN || true
HTTP_CODE="\$(curl -sS -o /tmp/${APP_NAME}-health.html -w '%{http_code}' "http://127.0.0.1:\$APP_PORT/" || true)"
echo "local_http: \$HTTP_CODE"
STATUS_SCRIPT

chmod +x "$APP/start.sh" "$APP/stop.sh" "$APP/status.sh"

"$APP/stop.sh"

if lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN >/tmp/${APP_NAME}-port.txt 2>&1; then
  echo "Port $APP_PORT is already in use:" >&2
  cat /tmp/${APP_NAME}-port.txt >&2
  exit 2
fi

nohup "$APP/start.sh" > "$APP/app.log" 2>&1 &
echo "$!" > "$APP/app.pid"

sleep 3
PID="$(cat "$APP/app.pid")"
if ! kill -0 "$PID" >/dev/null 2>&1; then
  echo "Application process exited during startup." >&2
  tail -120 "$APP/app.log" >&2 || true
  exit 1
fi

HTTP_CODE="$(curl -sS -o /tmp/${APP_NAME}-health.html -w '%{http_code}' "http://127.0.0.1:$APP_PORT/" || true)"
case "$HTTP_CODE" in
  200|302|303|405) ;;
  *)
    echo "Unexpected local health HTTP status: $HTTP_CODE" >&2
    tail -120 "$APP/app.log" >&2 || true
    exit 1
    ;;
esac

lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN
echo "local_http=$HTTP_CODE"
echo "deployed_release=$RELEASE"
echo "pid=$PID"
REMOTE_SCRIPT

  rm -f "$archive"
}

remote_control() {
  local command="$1"
  case "$command" in
    status)
      ssh_remote "if [ -x '$REMOTE_APP/status.sh' ]; then '$REMOTE_APP/status.sh'; else echo 'not deployed'; fi"
      ;;
    logs)
      ssh_remote "tail -f '$REMOTE_APP/app.log'"
      ;;
    stop)
      ssh_remote "if [ -x '$REMOTE_APP/stop.sh' ]; then '$REMOTE_APP/stop.sh'; fi"
      ;;
    start)
      ssh_remote "nohup '$REMOTE_APP/start.sh' > '$REMOTE_APP/app.log' 2>&1 & echo \$! > '$REMOTE_APP/app.pid'; sleep 2; '$REMOTE_APP/status.sh'"
      ;;
    restart)
      ssh_remote "if [ -x '$REMOTE_APP/stop.sh' ]; then '$REMOTE_APP/stop.sh'; fi; nohup '$REMOTE_APP/start.sh' > '$REMOTE_APP/app.log' 2>&1 & echo \$! > '$REMOTE_APP/app.pid'; sleep 2; '$REMOTE_APP/status.sh'"
      ;;
    health)
      ssh_remote "curl -sS -o /tmp/${APP_NAME}-health.html -w 'HTTP %{http_code}\n' 'http://127.0.0.1:$APP_PORT/'"
      ;;
  esac
}

case "$ACTION" in
  -h|--help|help)
    usage
    ;;
  deploy)
    deploy
    ;;
  status|logs|stop|start|restart|health)
    remote_control "$ACTION"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
