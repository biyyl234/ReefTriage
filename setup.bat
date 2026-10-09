@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM  ReefTriage + NocoBase 一键部署脚本 (Windows)
REM  用法: 双击运行 或 命令行执行 setup.bat
REM ============================================================

echo.
echo ============================================================
echo   ReefTriage + NocoBase 部署脚本
echo ============================================================
echo.

REM --- 检查项目目录 ---
cd /d "%~dp0"
echo [INFO] 项目目录: %CD%
echo.

REM ============================================================
REM  Step 1: Python 虚拟环境 + 依赖
REM ============================================================
echo [Step 1/6] 配置 Python 环境...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] 创建 Python 虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败，请确认已安装 Python 3.12+
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建成功
) else (
    echo [OK] 虚拟环境已存在
)

echo [INFO] 安装 Python 依赖...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install 失败
    pause
    exit /b 1
)
echo [OK] Python 依赖安装完成
echo.

REM ============================================================
REM  Step 2: PostgreSQL 检查
REM ============================================================
echo [Step 2/6] 检查 PostgreSQL...
echo.

set PG_FOUND=0
set PG_BIN=

REM 尝试常见安装路径
if exist "C:\Program Files\PostgreSQL\17\bin\psql.exe" (
    set PG_BIN=C:\Program Files\PostgreSQL\17\bin
    set PG_FOUND=1
)
if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    set PG_BIN=C:\Program Files\PostgreSQL\16\bin
    set PG_FOUND=1
)
if exist "C:\Program Files\PostgreSQL\15\bin\psql.exe" (
    set PG_BIN=C:\Program Files\PostgreSQL\15\bin
    set PG_FOUND=1
)
if exist "%USERPROFILE%\pg17\pgsql\bin\psql.exe" (
    set PG_BIN=%USERPROFILE%\pg17\pgsql\bin
    set PG_FOUND=1
)

REM 尝试 PATH 中的 psql
if "%PG_FOUND%"=="0" (
    where psql >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%i in ('where psql') do set PG_BIN=%%~dpi
        set PG_FOUND=1
    )
)

if "%PG_FOUND%"=="0" (
    echo [WARN] 未找到 PostgreSQL
    echo.
    echo  请选择安装方式:
    echo   1. 下载便携版 (推荐, 无需管理员权限)
    echo   2. 我已安装, 手动指定 bin 目录
    echo   3. 跳过 (后续手动配置)
    echo.
    set /p PG_CHOICE=请输入选项 [1/2/3]: 
    
    if "!PG_CHOICE!"=="1" (
        echo [INFO] 下载 PostgreSQL 17 便携版...
        if not exist "%USERPROFILE%\pg17" mkdir "%USERPROFILE%\pg17"
        powershell -Command "Invoke-WebRequest -Uri 'https://get.enterprisedb.com/postgresql/postgresql-17.0-1-windows-x64-binaries.zip' -OutFile '%USERPROFILE%\pg17\pg.zip'"
        if errorlevel 1 (
            echo [ERROR] 下载失败，请手动下载后重试
            echo   下载地址: https://www.enterprisedb.com/download-postgresql-binaries
            pause
            exit /b 1
        )
        echo [INFO] 解压中...
        powershell -Command "Expand-Archive -Path '%USERPROFILE%\pg17\pg.zip' -DestinationPath '%USERPROFILE%\pg17' -Force"
        set PG_BIN=%USERPROFILE%\pg17\pgsql\bin
        set PG_FOUND=1
        echo [OK] PostgreSQL 便携版已就绪
    )
    
    if "!PG_CHOICE!"=="2" (
        set /p PG_BIN=请输入 PostgreSQL bin 目录路径: 
        if exist "!PG_BIN!\psql.exe" (
            set PG_FOUND=1
        ) else (
            echo [ERROR] 找不到 psql.exe
            pause
            exit /b 1
        )
    )
)

if "%PG_FOUND%"=="1" (
    echo [OK] PostgreSQL 已找到: %PG_BIN%
) else (
    echo [WARN] 跳过 PostgreSQL 配置，请后续手动安装并创建 nocobase 数据库
)
echo.

REM ============================================================
REM  Step 3: 启动 PostgreSQL + 创建数据库
REM ============================================================
echo [Step 3/6] 配置 PostgreSQL 数据库...
echo.

if "%PG_FOUND%"=="1" (
    REM 检查 PostgreSQL 是否在运行
    "%PG_BIN%\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -c "SELECT 1;" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] PostgreSQL 未运行，尝试启动...
        
        REM 便携版: 检查 data 目录
        if exist "%USERPROFILE%\pg17\pgsql\bin\psql.exe" (
            if not exist "%USERPROFILE%\pg17\data" (
                echo [INFO] 初始化数据库集群...
                set PGPASSWORD=postgres
                "%PG_BIN%\initdb.exe" -D "%USERPROFILE%\pg17\data" -U postgres -W
            )
            echo [INFO] 启动 PostgreSQL...
            start "" "%PG_BIN%\pg_ctl.exe" -D "%USERPROFILE%\pg17\data" -l "%USERPROFILE%\pg17\pg.log" -o "-p 5432" start
            timeout /t 3 /nobreak >nul
        ) else (
            echo [INFO] 请手动启动 PostgreSQL 服务
            net start postgresql-x64-17 2>nul
            net start postgresql-x64-16 2>nul
            net start postgresql-x64-15 2>nul
            timeout /t 3 /nobreak >nul
        )
    )
    
    REM 创建 nocobase 数据库
    set PGPASSWORD=postgres
    "%PG_BIN%\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -c "SELECT 1 FROM pg_database WHERE datname='nocobase';" | findstr "nocobase" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] 创建 nocobase 数据库...
        "%PG_BIN%\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -c "CREATE DATABASE nocobase;"
        echo [OK] 数据库 nocobase 已创建
    ) else (
        echo [OK] 数据库 nocobase 已存在
    )
)
echo.

REM ============================================================
REM  Step 4: NocoBase 依赖安装
REM ============================================================
echo [Step 4/6] 安装 NocoBase 依赖...
echo.

if not exist "nocobase\node_modules" (
    echo [INFO] 这可能需要 10-20 分钟，请耐心等待...
    cd nocobase
    
    REM 检查 .env
    if not exist ".env" (
        echo [INFO] 从 .env.example 创建 .env...
        copy .env.example .env >nul
    )
    
    REM 检查 yarn
    where yarn >nul 2>&1
    if errorlevel 1 (
        echo [INFO] 安装 yarn...
        npm install -g yarn
    )
    
    echo [INFO] yarn install (使用国内镜像加速)...
    yarn config set registry https://registry.npmmirror.com >nul 2>&1
    call yarn install
    if errorlevel 1 (
        echo [ERROR] yarn install 失败
        cd ..
        pause
        exit /b 1
    )
    echo [OK] NocoBase 依赖安装完成
    cd ..
) else (
    echo [OK] NocoBase 依赖已安装
)
echo.

REM ============================================================
REM  Step 5: 初始化 NocoBase
REM ============================================================
echo [Step 5/6] 初始化 NocoBase...
echo.

cd nocobase

REM 检查是否已初始化 (通过检查数据库表)
set PGPASSWORD=postgres
if "%PG_FOUND%"=="1" (
    "%PG_BIN%\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -d nocobase -c "SELECT tablename FROM pg_tables WHERE tablename='users';" | findstr "users" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] 初始化 NocoBase 数据库...
        call yarn nocobase install
        if errorlevel 1 (
            echo [ERROR] NocoBase 初始化失败
            cd ..
            pause
            exit /b 1
        )
        echo [OK] NocoBase 初始化完成
    ) else (
        echo [OK] NocoBase 已初始化
    )
) else (
    echo [WARN] 跳过 NocoBase 初始化 (PostgreSQL 未配置)
)

cd ..
echo.

REM ============================================================
REM  Step 6: 数据同步
REM ============================================================
echo [Step 6/6] 同步礁段数据到 NocoBase...
echo.

REM 先启动 ReefTriage
echo [INFO] 启动 ReefTriage 后端...
start "" /B ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
timeout /t 5 /nobreak >nul

REM 启动 NocoBase
echo [INFO] 启动 NocoBase...
cd nocobase
start "" cmd /c "yarn dev"
cd ..
timeout /t 30 /nobreak >nul

echo [INFO] 执行数据同步...
".venv\Scripts\python.exe" scripts\sync_to_nocobase.py
if errorlevel 1 (
    echo [WARN] 数据同步失败，可稍后手动运行: scripts\sync_to_nocobase.py
) else (
    echo [OK] 数据同步完成
)

echo.
echo ============================================================
echo   部署完成！
echo ============================================================
echo.
echo   访问地址:
echo     ReefTriage:  http://127.0.0.1:8000
echo     NocoBase:    http://127.0.0.1:13000
echo     管理面板:    http://127.0.0.1:8000/admin-panel
echo.
echo   NocoBase 管理员:
echo     邮箱: admin@nocobase.com
echo     密码: admin123
echo.
echo   后续启动:
echo     start_all.bat   (启动所有服务)
echo     stop_all.bat    (停止所有服务)
echo.
echo ============================================================
echo.
pause
