@echo off
REM Setup Local Telegram Bot API Server
REM Usage: setup_local_api.bat <api_id> <api_hash> <bot_token>

setlocal

set API_ID=%1
set API_HASH=%2
set BOT_TOKEN=%3

if "%API_ID%"=="" (
    echo.
    echo Cu phap: setup_local_api.bat ^<api_id^> ^<api_hash^> ^<bot_token^>
    echo.
    echo Vi du: setup_local_api.bat 12345 abc123def456 1234:ABC-DEF
    echo.
    echo Lay api_id, api_hash tai: https://my.telegram.org
    exit /b 1
)

echo ========================================
echo  Setup Local Telegram Bot API Server
echo ========================================
echo.

REM Kiem tra Docker
echo [1/5] Kiem tra Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo FAILED: Docker chua duoc cai dat hoac chua chay
    exit /b 1
)
echo OK
echo.

REM Logout khoi API chinh
echo [2/5] Logout bot khoi API chinh...
curl -s -X POST "https://api.telegram.org/bot%BOT_TOKEN%/logOut"
echo.
echo.

REM Dung container cu neu co
echo [3/5] Dung container cu (neu co)...
docker rm -f telegram-bot-api >nul 2>&1
echo OK
echo.

REM Cho 10 giay truoc khi start (Telegram yeu cau cho)
echo [4/5] Cho 10 giay de Telegram xu ly logout...
timeout /t 10 /nobreak >nul
echo OK
echo.

REM Start container
echo [5/5] Start Docker container...
docker run -d ^
  --name telegram-bot-api ^
  --restart=always ^
  -p 8081:8081 ^
  -e TELEGRAM_API_ID=%API_ID% ^
  -e TELEGRAM_API_HASH=%API_HASH% ^
  -v telegram-bot-api-data:/var/lib/telegram-bot-api ^
  aiogram/telegram-bot-api:latest

if %ERRORLEVEL% neq 0 (
    echo FAILED: Khong start duoc container
    exit /b 1
)

echo.
echo ========================================
echo  Setup thanh cong!
echo ========================================
echo.
echo LUU Y: Phai cho them 10 phut nua roi moi test getMe
echo.
echo Test API:
echo   curl http://localhost:8081/bot%BOT_TOKEN%/getMe
echo.
echo Them vao file .env:
echo   TELEGRAM_LOCAL_API=http://localhost:8081
echo.
echo Cac lenh huu ich:
echo   docker logs telegram-bot-api     (xem log)
echo   docker restart telegram-bot-api  (restart)
echo   docker stop telegram-bot-api     (dung)
echo   docker start telegram-bot-api    (chay lai)
echo.

endlocal
