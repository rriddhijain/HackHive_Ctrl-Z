#!/usr/bin/env bash
# One command for the demo (SPEC §13 Round 1): checks -> Ollama up + model warm -> re-seed chat history -> dashboard
# build if stale -> app.server -> Chrome. Stops with a red error naming the fix if anything is missing.
#   ./run_demo.sh        Ctrl-C stops the server (Ollama keeps running, model stays loaded)
set -euo pipefail
cd "$(dirname "$0")"
T0=$(date +%s)
die() { printf '\n\033[31mrun_demo: %s\033[0m\n' "$*" >&2; exit 1; }
say() { printf '[%3ss] %s\n' "$(($(date +%s) - T0))" "$*"; }

command -v uv >/dev/null || die "uv not found: install uv, then run 'uv sync' in $(pwd)"
[ -d "/Applications/Google Chrome.app" ] || die "Google Chrome not found in /Applications (the demo runs in Chrome, not Safari)"
[ -f models/yolo26n.pt ] || die "models/yolo26n.pt missing: copy the weights from the dev Mac into models/"
read -r MODEL URL NUM_CTX < <(uv run --offline python -c \
  "from app.config import CFG; v = CFG['vlm']; print(v['model'], v['base_url'], v['num_ctx'])") \
  || die "Python environment not ready: run 'uv sync' in $(pwd)"
PY=.venv/bin/python
PID=$(lsof -tiTCP:8000 -sTCP:LISTEN || true)
[ -z "$PID" ] || die "port 8000 is in use by PID $PID ($(ps -o comm= -p "$PID")): stop it with 'kill $PID', then re-run"

if ! curl -sf "$URL/api/version" >/dev/null; then
  say "starting Ollama"
  open -a Ollama 2>/dev/null || die "Ollama is not installed (expected /Applications/Ollama.app)"
  for _ in $(seq 60); do curl -sf "$URL/api/version" >/dev/null && break; sleep 1; done
  curl -sf "$URL/api/version" >/dev/null || die "Ollama did not answer at $URL within 60 s (a stale 'ollama serve' holding the port? 'pkill -9 -f \"ollama serve\"; open -a Ollama')"
fi
curl -sf "$URL/api/tags" | grep -q "\"$MODEL\"" \
  || die "model $MODEL is not in Ollama: copy ~/.ollama/models from the dev Mac (a pull needs the captain's OK, D21)"
say "Ollama $(curl -sf "$URL/api/version" | sed 's/.*"version":"\([^"]*\)".*/\1/') up; warming up $MODEL"
# a fresh load: a long-running MLX runner keeps a buffer cache (4 GB model seen at 12 GB after a night of calls, D75)
curl -sf "$URL/api/generate" -d "{\"model\": \"$MODEL\", \"keep_alive\": 0}" >/dev/null || true
# same keep_alive / num_ctx / think as the pipeline (app/vlm.py), so its first real call doesn't reload the model
curl -sf -m 120 "$URL/api/chat" -d "{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"ok\"}],
  \"stream\": false, \"think\": false, \"keep_alive\": -1, \"options\": {\"num_predict\": 1, \"num_ctx\": $NUM_CTX}}" >/dev/null \
  || die "warm-up call to $MODEL failed (is another model hogging memory? check 'ollama ps')"
curl -sf "$URL/api/ps" | grep -q "\"$MODEL\"" || die "$MODEL answered but is not loaded ('ollama ps')"

say "re-seeding the chat history (seed() deletes the old seeded rows first; times relative to now)"
$PY -m scripts.seed_history

if [ ! -f web/dist/index.html ] || [ -n "$(find web/src web/scripts web/next.config.ts web/package.json web/postcss.config.mjs -newer web/dist/index.html)" ]; then
  [ -d web/node_modules ] || die "web/dist is missing or stale and web/node_modules is missing: copy web/dist from the dev Mac"
  say "building the dashboard"
  (cd web && npm run build >/dev/null) || die "dashboard build failed: run 'cd web && npm run build' to see why"
fi

say "starting the server"
$PY -m app.server &
SRV=$!
trap 'kill $SRV 2>/dev/null; wait $SRV 2>/dev/null' EXIT
for _ in $(seq 120); do
  curl -sf localhost:8000/api/metrics >/dev/null && break
  kill -0 $SRV 2>/dev/null || die "the server exited during start-up (its error is above)"
  sleep 0.5
done
curl -sf localhost:8000/ | grep -q 'id="root"' || die "the dashboard is not served at http://localhost:8000"
open -a "Google Chrome" http://localhost:8000
say "dashboard ready at http://localhost:8000 in Chrome (Ctrl-C stops the server)"
wait $SRV
