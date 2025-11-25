@echo off
chcp 65001 >nul
echo 🌍 Starting Athena Web UI...
echo.

cd frontend

REM Install dependencies automatically if missing
IF NOT EXIST node_modules (
    echo 📦 Installing dependencies...
    npm install
)

npm start
echo.
echo 🛑 UI stopped or crashed. Check frontend/ terminal logs.
pause
