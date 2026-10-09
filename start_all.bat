@echo off
chcp 65001 >nul
title ReefTriage + NocoBase 一键启动

echo ============================================================
echo   ReefTriage + NocoBase 全栈启动
echo ============================================================
echo.

REM --- 1. 启动 PostgreSQL (便携版) ---
echo [1/3] 启动 PostgreSQL (port 5432) ...
if exist "%USERPROFILE%\pg17\pgsql\bin\pg_ctl.exe" (
    "%USERPROFILE%\pg17\pgsql\bin\pg_ctl.exe" -D "%USERPROFILE%\pg17\data" -l "%USERPROFILE%\pg17\postgres.log" -o "-p 5432" start
    timeout /t 3 /nobreak >nul
) else (
    echo   警告: 未找到 PostgreSQL便携版, 跳过...
)

REM --- 2. 启动 ReefTriage ---
echo [2/3] 启动 ReefTriage (port 8000) ...
start "ReefTriage :8000" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul

REM --- 3. 启动 NocoBase ---
echo [3/3] 启动 NocoBase (port 13000) ...
start "NocoBase :13000" cmd /k "cd /d %~dp0\nocobase && yarn dev"

echo.
echo ============================================================
echo   启动中, 请稍候...
echo   ReefTriage: http://127.0.0.1:8000
echo   NocoBase:   http://127.0.0.1:13000
echo   管理员:     admin@nocobase.com / admin123
echo ============================================================
echo.
pause
