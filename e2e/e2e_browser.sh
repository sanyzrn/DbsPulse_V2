#!/bin/bash
# سناریوی مرورگریِ همکار: هر سه سرویس را بالا می‌آورد و e2e_browser.py را اجرا می‌کند.
# پیش‌نیاز: playwright نصب و مرورگرِ chromium دانلود شده باشد؛ setup_e2e.py یک‌بار اجرا شده باشد.
set -e
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-only-secret-change-me-0123456789abcdef}"
export ENABLE_SCHEDULER="${ENABLE_SCHEDULER:-false}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$(mktemp -d)"

cleanup() {
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "mock_llm.py" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  fuser -k 8000/tcp 2>/dev/null || true
  fuser -k 8100/tcp 2>/dev/null || true
  fuser -k 5173/tcp 2>/dev/null || true
}
trap cleanup EXIT
cleanup || true
sleep 1

python3 "$HERE/mock_llm.py" > "$LOGS/mock_llm.log" 2>&1 &
cd "$ROOT/backend" && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$LOGS/backend.log" 2>&1 &
cd "$ROOT/frontend" && npm run dev -- --port 5173 --strictPort > "$LOGS/frontend.log" 2>&1 &

python3 "$HERE/e2e_browser.py"
