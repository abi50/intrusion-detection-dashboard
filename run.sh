#!/usr/bin/env bash
# One-command start for the Intrusion Detection Dashboard.
# Builds the frontend (if needed) and starts the backend on port 8000.

set -e

cd "$(dirname "$0")"

echo "=== Intrusion Detection Dashboard ==="

# Install backend deps if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "[1/3] Installing backend dependencies..."
    pip install -r backend/requirements.txt
else
    echo "[1/3] Backend dependencies OK"
fi

# Build frontend if dist doesn't exist
if [ ! -f frontend/dist/index.html ]; then
    echo "[2/3] Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
else
    echo "[2/3] Frontend build OK"
fi

echo "[3/3] Starting server on http://localhost:8000"
echo ""
echo "  Dashboard:  http://localhost:8000"
echo "  API:        http://localhost:8000/api/status"
echo ""
echo "  To run the attack simulator (separate terminal):"
echo "    python -m simulator.simulate"
echo ""

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
