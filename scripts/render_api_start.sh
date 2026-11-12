#!/bin/sh
set -eu

api_port="${PORT:-10000}"
simulator_port="${GIGSIM_PORT:-8081}"
api_pid=""

cleanup() {
  if [ -n "$api_pid" ]; then
    kill "$api_pid" 2>/dev/null || true
  fi
  kill "$simulator_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

uvicorn apps.simulator.main:app --host 127.0.0.1 --port "$simulator_port" &
simulator_pid=$!

attempt=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${simulator_port}/health', timeout=1)" >/dev/null 2>&1
do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ] || ! kill -0 "$simulator_pid" 2>/dev/null; then
    echo "GigSim failed to become healthy" >&2
    exit 1
  fi
  sleep 1
done

uvicorn apps.api.main:app --host 0.0.0.0 --port "$api_port" &
api_pid=$!
wait "$api_pid"
