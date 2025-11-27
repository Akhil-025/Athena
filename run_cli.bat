@echo off
chcp 65001 >nul
echo 💬 Starting Athena CLI...
echo.

REM Activate rag_env virtual environment
call rag_env\Scripts\activate.bat

python main.py
echo.
echo 🛑 CLI closed or exited.
pause