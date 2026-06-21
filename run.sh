#!/usr/bin/env bash
#
# run.sh — start / stop / manage the Toni & Sheriff app and its services.
#
#   ./run.sh start      Start Docker VM (colima), Postgres and Ollama (each only
#                       if needed), then launch the Streamlit app (detached).
#   ./run.sh stop       Stop the Streamlit app (leaves services running).
#   ./run.sh restart    Stop then start the app.
#   ./run.sh status      Show the state of every component.
#   ./run.sh logs        Tail the app log.
#   ./run.sh down        Stop the app AND the Postgres container.
#   ./run.sh shutdown    Full teardown — symmetric to start: stop the app,
#                       Postgres, the Docker VM (colima) AND Ollama.
#
# Env overrides:  PORT (default 8501)
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-8501}"
PY="$DIR/.venv/bin/python"
STREAMLIT="$DIR/.venv/bin/streamlit"
LOG="/tmp/local-ai-agents.streamlit.log"
PIDFILE="/tmp/local-ai-agents.streamlit.pid"
URL="http://localhost:${PORT}"

c_green() { printf "\033[32m%s\033[0m\n" "$1"; }
c_yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
c_red() { printf "\033[31m%s\033[0m\n" "$1"; }

app_pid() {
  # Prints the running Streamlit PID (if any), else nothing.
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    cat "$PIDFILE"
  else
    pgrep -f "streamlit run app.py" 2>/dev/null | head -1 || true
  fi
}

ensure_services() {
  # Docker VM (colima)
  if ! colima status >/dev/null 2>&1; then
    c_yellow "Starting Docker VM (colima)…"
    colima start
  fi
  # Postgres / pgvector
  if ! docker ps --format '{{.Names}}' | grep -q '^local-pgvector$'; then
    c_yellow "Starting Postgres (pgvector)…"
    docker compose up -d
  fi
  printf "Waiting for Postgres"
  for _ in $(seq 1 30); do
    if docker exec local-pgvector pg_isready -U agent_user -d agent_db >/dev/null 2>&1; then
      printf " ready\n"; break
    fi
    printf "."; sleep 1
  done
  # Schema (idempotent)
  "$PY" -m scripts.init_db >/dev/null 2>&1 && c_green "Postgres schema ready."
  # Ollama
  if ! curl -s "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    c_yellow "Starting Ollama…"
    brew services start ollama >/dev/null 2>&1 || true
    sleep 2
  fi
  if curl -s "http://localhost:11434/api/tags" 2>/dev/null | grep -q "gemma3"; then
    c_green "Ollama up (gemma3 available)."
  else
    c_yellow "Ollama up, but gemma3:12b not found — run: ollama pull gemma3:12b"
  fi
}

start() {
  if [ -n "$(app_pid)" ]; then
    c_yellow "App already running at $URL (pid $(app_pid))."
    exit 0
  fi
  [ -x "$STREAMLIT" ] || { c_red "Missing $STREAMLIT — run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
  ensure_services
  c_yellow "Launching Streamlit…"
  nohup "$STREAMLIT" run app.py --server.headless true --server.port "$PORT" \
    > "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  disown 2>/dev/null || true
  for _ in $(seq 1 30); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null)" = "200" ]; then
      c_green "App running at $URL  (pid $(cat "$PIDFILE"), logs: $LOG)"
      exit 0
    fi
    sleep 1
  done
  c_red "App did not become ready — check the log: tail -f $LOG"
  exit 1
}

stop() {
  pid="$(app_pid)"
  if [ -z "$pid" ]; then
    c_yellow "App is not running."
  else
    kill "$pid" 2>/dev/null || true
    pkill -f "streamlit run app.py" 2>/dev/null || true
    c_green "Stopped the app (pid $pid)."
  fi
  rm -f "$PIDFILE"
}

status() {
  echo "Toni & Sheriff — status"
  colima status >/dev/null 2>&1 && c_green "  Docker VM (colima): running" || c_red "  Docker VM (colima): stopped"
  docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^local-pgvector$' \
    && c_green "  Postgres:           running" || c_red "  Postgres:           stopped"
  curl -s http://localhost:11434/api/tags >/dev/null 2>&1 \
    && c_green "  Ollama:             running" || c_red "  Ollama:             stopped"
  if [ -n "$(app_pid)" ]; then c_green "  Streamlit app:      running ($URL, pid $(app_pid))"; else c_red "  Streamlit app:      stopped"; fi
}

shutdown() {
  # Symmetric counterpart to `start`: tear everything down.
  stop
  c_yellow "Stopping Postgres…"
  docker compose down 2>/dev/null || true
  c_yellow "Stopping Docker VM (colima)…"
  colima stop 2>/dev/null || true
  c_yellow "Stopping Ollama…"
  brew services stop ollama >/dev/null 2>&1 || true
  c_green "All components stopped."
}

case "${1:-}" in
  start)    start ;;
  stop)     stop ;;
  restart)  stop; sleep 1; start ;;
  status)   status ;;
  logs)     tail -f "$LOG" ;;
  down)     stop; c_yellow "Stopping Postgres…"; docker compose down ;;
  shutdown) shutdown ;;
  *)
    echo "Usage: ./run.sh {start|stop|restart|status|logs|down|shutdown}"
    exit 1
    ;;
esac
