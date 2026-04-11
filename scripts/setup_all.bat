@echo off
REM Auto setup tất cả: tải NSSM + cài Windows Service
REM Chạy với quyền Administrator
REM
REM Cách dùng:
REM   setup_all.bat                                → dùng thư mục hiện tại làm BOT_DIR
REM   setup_all.bat D:\Code\report_mkt_bot         → chỉ định BOT_DIR

setlocal EnableDelayedExpansion

REM ===== Config =====
set SERVICE_NAME=ReportMktBot
set NSSM_VERSION=2.24
set NSSM_URL=https://nssm.cc/release/nssm-%NSSM_VERSION%.zip

REM ===== Xác định BOT_DIR =====
set BOT_DIR=%~1
if "%BOT_DIR%"=="" (
    set BOT_DIR=%~dp0..
)

REM Resolve absolute path
for %%i in ("%BOT_DIR%") do set BOT_DIR=%%~fi

REM ===== Kiểm tra quyền Administrator =====
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Script nay can chay voi quyen Administrator.
    echo Right-click -^> Run as administrator
    pause
    exit /b 1
)

echo ========================================
echo  Auto Setup Report MKT Bot Service
echo ========================================
echo  BOT_DIR: %BOT_DIR%
echo  SERVICE: %SERVICE_NAME%
echo ========================================
echo.

REM ===== Kiem tra main.py hoac .exe =====
set USE_EXE=0
if exist "%BOT_DIR%\dist\report_mkt_bot.exe" (
    set USE_EXE=1
    set APP_PATH=%BOT_DIR%\dist\report_mkt_bot.exe
    echo [1/6] Tim thay report_mkt_bot.exe
) else if exist "%BOT_DIR%\main.py" (
    set APP_PATH=%BOT_DIR%\main.py
    echo [1/6] Tim thay main.py
) else (
    echo [ERROR] Khong tim thay main.py hoac report_mkt_bot.exe trong %BOT_DIR%
    pause
    exit /b 1
)
echo.

REM ===== Kiem tra .env =====
echo [2/6] Kiem tra file .env...
if not exist "%BOT_DIR%\.env" (
    echo [WARNING] Khong tim thay file .env trong %BOT_DIR%
    echo Vui long tao file .env tu .env.example va dien cac bien moi truong
    echo.
    echo Tiep tuc? [Y/N]
    set /p CONTINUE=
    if /i not "!CONTINUE!"=="Y" exit /b 1
)
echo OK
echo.

REM ===== Tai NSSM neu chua co =====
set NSSM_EXE=%~dp0nssm.exe
echo [3/6] Kiem tra NSSM...

where nssm >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set NSSM_EXE=nssm
    echo NSSM da co trong PATH
    goto :nssm_ready
)

if exist "%NSSM_EXE%" (
    echo NSSM da co tai %NSSM_EXE%
    goto :nssm_ready
)

echo Tai NSSM...
set NSSM_ZIP=%TEMP%\nssm.zip
set NSSM_TMP=%TEMP%\nssm-%NSSM_VERSION%

REM Xoa temp cu
if exist "!NSSM_TMP!" rmdir /s /q "!NSSM_TMP!"
if exist "!NSSM_ZIP!" del /q "!NSSM_ZIP!"

REM Thu nhieu URL (nssm.cc hay bi down)
set DOWNLOAD_OK=0

echo Thu nssm.cc...
powershell -Command "try { Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '!NSSM_ZIP!' -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% equ 0 (
    set DOWNLOAD_OK=1
    goto :nssm_downloaded
)

echo Thu GitHub mirror 1...
powershell -Command "try { Invoke-WebRequest -Uri 'https://github.com/Cthulhu-throwaway/nssm-mirror/releases/download/2.24/nssm-2.24.zip' -OutFile '!NSSM_ZIP!' -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% equ 0 (
    set DOWNLOAD_OK=1
    goto :nssm_downloaded
)

echo Thu Chocolatey mirror...
powershell -Command "try { Invoke-WebRequest -Uri 'https://packages.chocolatey.org/NSSM.2.24.0.20180307.nupkg' -OutFile '%TEMP%\nssm.nupkg' -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop; Expand-Archive -Path '%TEMP%\nssm.nupkg' -DestinationPath '%TEMP%\nssm-choco' -Force; exit 0 } catch { exit 1 }"
if %ERRORLEVEL% equ 0 (
    if exist "%TEMP%\nssm-choco\tools\nssm.exe" (
        copy /y "%TEMP%\nssm-choco\tools\nssm.exe" "%NSSM_EXE%" >nul
        rmdir /s /q "%TEMP%\nssm-choco" 2>nul
        del /q "%TEMP%\nssm.nupkg" 2>nul
        echo Copied NSSM tu Chocolatey to %NSSM_EXE%
        goto :nssm_ready
    )
)

REM Khong tai duoc
echo.
echo [ERROR] Khong tai duoc NSSM tu bat ky source nao
echo.
echo Vui long tai thu cong:
echo   1. Vao https://nssm.cc/download
echo   2. Tai nssm-2.24.zip
echo   3. Giai nen, copy win64\nssm.exe vao:
echo      %~dp0nssm.exe
echo   4. Chay lai script
echo.
pause
exit /b 1

:nssm_downloaded
REM Giai nen file zip
powershell -Command "Expand-Archive -Path '!NSSM_ZIP!' -DestinationPath '%TEMP%' -Force"

if exist "%TEMP%\nssm-%NSSM_VERSION%\win64\nssm.exe" (
    copy /y "%TEMP%\nssm-%NSSM_VERSION%\win64\nssm.exe" "%NSSM_EXE%" >nul
    echo Copied NSSM to %NSSM_EXE%
) else (
    echo [ERROR] Khong tim thay nssm.exe sau khi giai nen
    pause
    exit /b 1
)

REM Cleanup
del /q "!NSSM_ZIP!" 2>nul
rmdir /s /q "%TEMP%\nssm-%NSSM_VERSION%" 2>nul

:nssm_ready
echo.

REM ===== Xoa service cu neu co =====
echo [4/6] Dung va xoa service cu (neu co)...
"%NSSM_EXE%" stop %SERVICE_NAME% >nul 2>&1
"%NSSM_EXE%" remove %SERVICE_NAME% confirm >nul 2>&1
echo OK
echo.

REM ===== Cai dat service moi =====
echo [5/6] Cai dat service %SERVICE_NAME%...

if %USE_EXE% equ 1 (
    "%NSSM_EXE%" install %SERVICE_NAME% "%APP_PATH%"
) else (
    REM Tim python - skip Microsoft Store stub (fake python)
    set PYTHON_PATH=
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set "LINE=%%i"
        echo !LINE! | findstr /i "WindowsApps" >nul
        if errorlevel 1 (
            if "!PYTHON_PATH!"=="" set "PYTHON_PATH=!LINE!"
        )
    )

    if "!PYTHON_PATH!"=="" (
        echo [ERROR] Khong tim thay python that trong PATH
        echo Luu y: Microsoft Store python stub se bi skip
        echo Vui long cai Python tu python.org va them vao PATH
        pause
        exit /b 1
    )

    echo Python path: !PYTHON_PATH!
    "%NSSM_EXE%" install %SERVICE_NAME% "!PYTHON_PATH!" "%APP_PATH%"
)

REM Cau hinh service
"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%BOT_DIR%"
"%NSSM_EXE%" set %SERVICE_NAME% DisplayName "Report MKT Bot"
"%NSSM_EXE%" set %SERVICE_NAME% Description "Telegram bot for reports and auto builds"
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Auto restart khi crash (delay 5s)
"%NSSM_EXE%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppRestartDelay 5000

REM Log stdout/stderr ra file, rotate khi > 10MB
"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%BOT_DIR%\service-stdout.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%BOT_DIR%\service-stderr.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 10485760

echo OK
echo.

REM ===== Start service =====
echo [6/6] Starting service...
"%NSSM_EXE%" start %SERVICE_NAME%
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Service chua start duoc. Kiem tra log:
    echo   type "%BOT_DIR%\service-stderr.log"
) else (
    echo Service da start thanh cong
)
echo.

echo ========================================
echo  Setup hoan tat!
echo ========================================
echo.
echo Service:   %SERVICE_NAME%
echo Bot dir:   %BOT_DIR%
echo Stdout:    %BOT_DIR%\service-stdout.log
echo Stderr:    %BOT_DIR%\service-stderr.log
echo.
echo Cac lenh huu ich:
echo   "%NSSM_EXE%" status %SERVICE_NAME%
echo   "%NSSM_EXE%" stop %SERVICE_NAME%
echo   "%NSSM_EXE%" start %SERVICE_NAME%
echo   "%NSSM_EXE%" restart %SERVICE_NAME%
echo.
echo Hoac dung Windows Services (services.msc) de quan ly GUI
echo.
pause

endlocal
