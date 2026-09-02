@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    py -3 launch.py %*
    set "EXIT_CODE=%ERRORLEVEL%"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python 3 is not installed. Install Python 3.11 or newer, then run this launcher again.
        set "EXIT_CODE=1"
    ) else (
        python launch.py %*
        set "EXIT_CODE=%ERRORLEVEL%"
    )
)

if not "%EXIT_CODE%"=="0" (
    echo.
    pause
)

exit /b %EXIT_CODE%
