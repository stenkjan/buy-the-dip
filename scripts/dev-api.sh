#!/usr/bin/env bash
# Dev helper: start the buy-the-dip admin API locally with a generated admin
# key and print it, so you can paste it into the dashboard's "Admin API key"
# field (Bots tab). No key to "get" from anywhere — it's a shared secret you
# choose; this just picks a random one for you.
#
# Usage:
#   ./scripts/dev-api.sh                 # random key, port 8000
#   API_KEY=letmein ./scripts/dev-api.sh # reuse a fixed key
#   PORT=9000 ./scripts/dev-api.sh       # different port
set -euo pipefail

# Run from the repo root so `apps.api.main` is importable.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8000}"
export API_CORS_ORIGINS="${API_CORS_ORIGINS:-http://localhost:5173}"

# Generate a key unless one was provided.
if [ -z "${API_KEY:-}" ]; then
  if command -v openssl >/dev/null 2>&1; then
    API_KEY="$(openssl rand -hex 16)"
  else
    API_KEY="$(python -c 'import secrets; print(secrets.token_hex(16))')"
  fi
fi
export API_KEY

cat <<EOF

  buy-the-dip — admin API (dev)
  ---------------------------------------------------------------
  Admin API key : ${API_KEY}
      → paste this into the dashboard's "Admin API key" field (Bots tab)
  API URL       : http://localhost:${PORT}
  Interactive   : http://localhost:${PORT}/docs
  CORS origin   : ${API_CORS_ORIGINS}
  ---------------------------------------------------------------
  Then, in another terminal:  cd apps/web && npm install && npm run dev

EOF

if ! python -c "import uvicorn" >/dev/null 2>&1; then
  echo "uvicorn not found — run 'pip install -e .' first." >&2
  exit 1
fi

exec python -m uvicorn apps.api.main:app --port "${PORT}" --reload
