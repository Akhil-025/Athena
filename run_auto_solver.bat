@echo off
chcp 65001 >nul
echo 🤖 Starting Athena Auto PYQ Solver...
echo.

REM call venv\Scripts\activate

python auto_solver.py
echo.
echo 📝 Auto Solver finished or exited. Check output folder.
pause
