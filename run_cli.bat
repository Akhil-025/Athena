@echo off
chcp 65001 >nul
echo 💬 Starting Athena CLI...
echo.

REM call venv\Scripts\activate

python main.py
echo.
echo 🛑 CLI closed or exited.
pause
