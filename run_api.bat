@echo off
chcp 65001 >nul
echo 🚀 Starting Athena API Server...
echo.

REM Activate virtual environment (optional - uncomment if you use it)
REM call venv\Scripts\activate

python flask_api_server.py
echo.
echo ❗ Server stopped or crashed. Check logs in ./logs folder.
pause
