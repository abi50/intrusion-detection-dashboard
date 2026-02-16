@echo off
REM One-command start for the Intrusion Detection Dashboard.
REM Builds the frontend (if needed) and starts the backend on port 8000.

cd /d "%~dp0"

echo === Intrusion Detection Dashboard ===

REM Install backend deps if needed
python -c "import fastapi" 2>NUL
if errorlevel 1 (
    echo [1/3] Installing backend dependencies...
    pip install -r backend\requirements.txt
) else (
    echo [1/3] Backend dependencies OK
)

REM Build frontend if dist doesn't exist
if not exist frontend\dist\index.html (
    echo [2/3] Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
) else (
    echo [2/3] Frontend build OK
)

echo [3/3] Starting server on http://localhost:8000
echo.
echo   Dashboard:  http://localhost:8000
echo   API:        http://localhost:8000/api/status
echo.
echo   To run the attack simulator (separate terminal):
echo     python -m simulator.simulate
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
