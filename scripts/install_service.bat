@echo off
REM Cài đặt report_mkt_bot làm Windows Service với NSSM
REM Service sẽ tự restart khi bot crash và auto-start khi boot máy
REM
REM Yêu cầu:
REM   1. Tải NSSM từ https://nssm.cc/download và thêm vào PATH
REM      (hoặc copy nssm.exe vào cùng thư mục với script này)
REM   2. File .env đã cấu hình sẵn cùng thư mục với main.py hoặc .exe
REM
REM Cách dùng:
REM   install_service.bat <đường dẫn tuyệt đối tới bot folder>
REM
REM Ví dụ:
REM   install_service.bat D:\Code\report_mkt_bot

setlocal

set SERVICE_NAME=ReportMktBot
set BOT_DIR=%1

if "%BOT_DIR%"=="" (
    echo Cu phap: install_service.bat ^<bot_folder_path^>
    echo.
    echo Vi du: install_service.bat D:\Code\report_mkt_bot
    exit /b 1
)

if not exist "%BOT_DIR%\main.py" (
    if not exist "%BOT_DIR%\report_mkt_bot.exe" (
        echo Khong tim thay main.py hoac report_mkt_bot.exe trong %BOT_DIR%
        exit /b 1
    )
)

REM Kiem tra NSSM
where nssm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if not exist "%~dp0nssm.exe" (
        echo NSSM khong duoc tim thay. Tai tu: https://nssm.cc/download
        exit /b 1
    )
    set NSSM=%~dp0nssm.exe
) else (
    set NSSM=nssm
)

echo ========================================
echo  Cai dat %SERVICE_NAME% service
echo ========================================
echo.

REM Xoa service cu neu co
%NSSM% stop %SERVICE_NAME% >nul 2>&1
%NSSM% remove %SERVICE_NAME% confirm >nul 2>&1

REM Uu tien dung .exe neu co, khong thi dung python main.py
if exist "%BOT_DIR%\report_mkt_bot.exe" (
    echo Cai dat voi report_mkt_bot.exe
    %NSSM% install %SERVICE_NAME% "%BOT_DIR%\report_mkt_bot.exe"
) else (
    echo Cai dat voi python main.py
    for /f "delims=" %%i in ('where python') do set PYTHON=%%i
    %NSSM% install %SERVICE_NAME% "%PYTHON%" "%BOT_DIR%\main.py"
)

REM Cau hinh service
%NSSM% set %SERVICE_NAME% AppDirectory "%BOT_DIR%"
%NSSM% set %SERVICE_NAME% DisplayName "Report MKT Bot"
%NSSM% set %SERVICE_NAME% Description "Telegram bot for reports and auto builds"
%NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Auto restart khi crash
%NSSM% set %SERVICE_NAME% AppExit Default Restart
%NSSM% set %SERVICE_NAME% AppRestartDelay 5000

REM Log stdout/stderr ra file
%NSSM% set %SERVICE_NAME% AppStdout "%BOT_DIR%\service-stdout.log"
%NSSM% set %SERVICE_NAME% AppStderr "%BOT_DIR%\service-stderr.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760

REM Start service
%NSSM% start %SERVICE_NAME%

echo.
echo ========================================
echo  Cai dat thanh cong!
echo ========================================
echo.
echo Cac lenh huu ich:
echo   nssm status %SERVICE_NAME%    - Xem trang thai
echo   nssm stop %SERVICE_NAME%      - Dung service
echo   nssm start %SERVICE_NAME%     - Chay lai
echo   nssm restart %SERVICE_NAME%   - Restart
echo   nssm remove %SERVICE_NAME% confirm - Xoa service
echo.
echo Hoac dung Windows Services (services.msc) de quan ly GUI
echo.
echo Log:
echo   %BOT_DIR%\service-stdout.log
echo   %BOT_DIR%\service-stderr.log
echo.

endlocal
