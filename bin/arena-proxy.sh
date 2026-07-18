#!/usr/bin/env bash
# Manage a local translation proxy for models with no native
# Anthropic-compatible endpoint (first user: gpt-5.6-sol via LiteLLM).
#
# usage: arena-proxy.sh start|stop|status <model>
#
# Reads env/litellm.<model>.yaml, binds 127.0.0.1 only, logs and pidfile in
# .proxy/ (gitignored). The upstream API key is pulled from ~/.secrets in a
# subshell at launch and exported only to the proxy process, never to the
# harness or the contestant.
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CMD="${1:?usage: arena-proxy.sh start|stop|status <model>}"
MODEL="${2:?model name, e.g. gpt-5.6-sol}"
DIR="$ROOT/.proxy"
mkdir -p "$DIR"
PIDFILE="$DIR/$MODEL.pid"
LOG="$DIR/$MODEL.log"
CFG="$ROOT/env/litellm.$MODEL.yaml"
PORT="${ARENA_PROXY_PORT:-4100}"

alive() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "$CMD" in
  start)
    [[ -f "$CFG" ]] || { echo "no proxy config: $CFG" >&2; exit 1; }
    if alive; then echo "already running (pid $(cat "$PIDFILE"))"; exit 0; fi
    KEY=$(. "$HOME/.secrets" >/dev/null 2>&1; printf %s "${OPENAI_API_KEY:-}")
    [[ -n "$KEY" ]] || { echo "OPENAI_API_KEY not in environment or ~/.secrets" >&2; exit 1; }
    OPENAI_API_KEY="$KEY" nohup litellm --config "$CFG" \
      --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    for _ in $(seq 1 30); do
      sleep 1
      curl -sf "http://127.0.0.1:$PORT/health/liveliness" >/dev/null 2>&1 && { echo "proxy up on 127.0.0.1:$PORT (pid $(cat "$PIDFILE"), litellm $(litellm --version 2>/dev/null | grep -o '[0-9.]*$'))"; exit 0; }
      alive || break
    done
    echo "proxy failed to start; tail of $LOG:" >&2
    tail -5 "$LOG" >&2
    exit 1
    ;;
  stop)
    if alive; then kill "$(cat "$PIDFILE")" && rm -f "$PIDFILE" && echo stopped; else echo "not running"; rm -f "$PIDFILE"; fi
    ;;
  status)
    if alive && curl -sf "http://127.0.0.1:$PORT/health/liveliness" >/dev/null 2>&1; then
      echo "running (pid $(cat "$PIDFILE"), port $PORT)"
    else
      echo "not running"; exit 1
    fi
    ;;
  *)
    echo "usage: arena-proxy.sh start|stop|status <model>" >&2
    exit 1
    ;;
esac
