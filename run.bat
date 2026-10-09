@echo off
REM ReefTriage 启动脚本 (Windows)
REM 用法: 双击或在命令行运行 run.bat

cd /d "%~dp0"

REM 优先使用项目内 .venv
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo ============================================
echo   ReefTriage - Semporna Reef Prioritization
echo   Backend: http://127.0.0.1:8000
echo ============================================

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
