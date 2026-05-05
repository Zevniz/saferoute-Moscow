#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚦 SafeRoute startup"

# Helper functions
check_cmd() {
  local cmd="$1"
  local install_hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ $cmd is required but not found."
    if [[ -n "$install_hint" ]]; then
      echo "   $install_hint"
    fi
    exit 1
  fi
}

check_port() {
  local port="$1"
  local service="$2"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "⚠️  Port $port ($service) is already in use. Stack may already be running."
  else
    echo "✅ Port $port ($service) is free"
  fi
}

wait_for_url() {
  local url="$1"
  local service="$2"
  local max_attempts="${3:-30}"
  local attempt=1
  
  echo "⏳ Waiting for $service at $url"
  
  while [[ $attempt -le $max_attempts ]]; do
    if curl -s --max-time 5 "$url" >/dev/null 2>&1; then
      echo "✅ $service is ready"
      return 0
    fi
    
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
    ((attempt++))
  done
  
  echo "❌ $service failed to respond after $max_attempts attempts"
  echo "   Check logs: npm run logs"
  echo "   Current status:"
  docker compose ps
  exit 1
}

# Prerequisites check
check_cmd docker "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
check_cmd npm "Install Node.js from https://nodejs.org/"

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "❌ Docker Compose is not available."
  exit 1
fi

# Setup environment
if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "✅ Created .env from .env.example"
fi

# Check ports
check_port 5173 "frontend"
check_port 8000 "backend API"
check_port 5434 "postgres"
check_port 2322 "photon"
check_port 8002 "valhalla"

# Check data files
if [[ ! -f data/osm/moscow-oblast.osm.pbf ]]; then
  echo "⚠️  Missing data/osm/moscow-oblast.osm.pbf"
  echo "   Routes may not fully work until OSM data is available."
  echo "   Put the file here: data/osm/moscow-oblast.osm.pbf"
  echo "   Or run the project bootstrap/data setup command if available."
fi

# Start services
echo "🚀 Starting SafeRoute stack..."
docker compose up --build -d

# Wait for services
wait_for_url "http://127.0.0.1:8000/api/health?deep=false" "backend" 60
wait_for_url "http://127.0.0.1:5173" "frontend" 30

# Enrichment check if available
if npm run --silent enrichment:check >/dev/null 2>&1; then
  echo "✅ Enrichment check passed"
else
  echo "⚠️  Enrichment check reported warnings. Routes may still work with base graph."
fi

cat <<EOF

✅ SafeRoute is running!

Frontend:       http://localhost:5173
Backend health: http://localhost:8000/api/health
API docs:       http://localhost:8000/docs

Commands:
  Stop stack:    npm run stop
  View logs:     npm run logs
  Check health:  npm run health
  Reset stack:   npm run reset

EOF
