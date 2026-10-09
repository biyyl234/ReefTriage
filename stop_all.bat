@echo off
chcp 65001 >nul
title 停止所有服务

echo ============================================================
echo   停止 ReefTriage + NocoBase + PostgreSQL
echo ============================================================
echo.

echo [1/3] 停止 NocoBase ...
taskkill /F /IM node.exe /FI "WINDOWTITLE eq NocoBase*" 2>nul
taskkill /F /IM node.exe 2>nul

echo [2/3] 停止 ReefTriage ...
taskkill /F /FI "WINDOWTITLE eq ReefTriage*" 2>nul

echo [3/3] 停止 PostgreSQL ...
if exist "%USERPROFILE%\pg17\pgsql\bin\pg_ctl.exe" (
    "%USERPROFILE%\pg17\pgsql\bin\pg_ctl.exe" -D "%USERPROFILE%\pg17\data" stop
)

echo.
echo 所有服务已停止
pause
