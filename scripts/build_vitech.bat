@echo off
REM Build script for Vitech
REM Usage: build_vitech.bat <variant> <branch>
REM Working directory: D:\Code

set VARIANT=%1
set BRANCH=%2

if "%VARIANT%"=="" set VARIANT=staging
if "%BRANCH%"=="" set BRANCH=main

echo ========================================
echo  Vitech Build
echo  Variant: %VARIANT%
echo  Branch: %BRANCH%
echo  Working dir: %CD%
echo  Time: %DATE% %TIME%
echo ========================================

REM --- Reset local changes ---
echo [1/6] Git reset...
git reset --hard
if %ERRORLEVEL% neq 0 (
    echo FAILED: git reset
    exit /b 1
)

REM --- Fetch latest ---
echo [2/6] Git fetch...
git fetch --all --prune
if %ERRORLEVEL% neq 0 (
    echo FAILED: git fetch
    exit /b 1
)

REM --- Checkout branch and pull ---
echo [3/6] Checkout %BRANCH% and pull...
git checkout %BRANCH%
git pull --all --prune
if %ERRORLEVEL% neq 0 (
    echo FAILED: git pull
    exit /b 1
)

REM --- Install dependencies ---
echo [4/6] Yarn install...
call yarn
if %ERRORLEVEL% neq 0 (
    echo FAILED: yarn install
    exit /b 1
)

REM --- Run vitech ---
echo [5/6] Yarn vitech...
call yarn vitech
if %ERRORLEVEL% neq 0 (
    echo FAILED: yarn vitech
    exit /b 1
)

REM --- Build ---
echo [6/6] Yarn build:win:zip...
call yarn build:win:zip
if %ERRORLEVEL% neq 0 (
    echo FAILED: yarn build:win:zip
    exit /b 1
)

echo ========================================
echo  Build completed successfully!
echo  Time: %DATE% %TIME%
echo ========================================
exit /b 0
