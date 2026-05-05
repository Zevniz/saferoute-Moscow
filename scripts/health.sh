#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🩺 SafeRoute health check"

check_service() {
  local url="$1"
  local service="$2"
  local expected_status="${3:-200}"
  
  echo -n "  $service: "
  
    if curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
    echo "✅ responds"
    return 0
  else
    echo "❌ not responding"
    return 1
  fi
}

errors=0

# Check services
check_service "http://127.0.0.1:5173" "Frontend" || ((errors++))
check_service "http://127.0.0.1:8000/api/health?deep=false" "Backend health" || ((errors++))
check_service "http://127.0.0.1:8000/api/health?deep=true" "Deep health" || ((errors++))

# Check enrichment if available
echo -n "  Enrichment: "
if npm run --silent enrichment:check >/dev/null 2>&1; then
  echo "✅ active"
else
  echo "⚠️  warnings (routes may still work)"
fi

# Docker services
echo ""
echo "🐳 Docker services:"
docker compose ps --format "table {{.Name}}	{{.Service}}	{{.Status}}"

echo ""
if [[ $errors -eq 0 ]]; then
  echo "✅ All services healthy"
  exit 0
else
  echo "❌ $errors service(s) not responding"
  echo "   Check logs: npm run logs"
  exit 1
fi
