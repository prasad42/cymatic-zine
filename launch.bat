@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

rem CMD cannot use a WSL UNC path as its working directory. Run through WSL instead.
if /i "%SCRIPT_DIR:~0,16%"=="\\wsl.localhost\" goto wsl
if /i "%SCRIPT_DIR:~0,7%"=="\\wsl$\" goto wsl

cd /d "%SCRIPT_DIR%"
if errorlevel 1 (
    echo Could not change to the application folder.
    exit /b 1
)

goto native

:wsl
where wsl.exe >nul 2>&1
if errorlevel 1 (
    echo WSL is not installed or wsl.exe is not available.
    exit /b 1
)

set "WSL_LOCATION=%SCRIPT_DIR:~16%"
if /i "%SCRIPT_DIR:~0,7%"=="\\wsl$\" set "WSL_LOCATION=%SCRIPT_DIR:~7%"
for /f "tokens=1,* delims=\" %%A in ("%WSL_LOCATION%") do (
    set "WSL_DISTRO=%%A"
    set "WSL_PATH=%%B"
)
set "WSL_PATH=/%WSL_PATH:\=/%"

wsl.exe -d "%WSL_DISTRO%" --cd "%WSL_PATH%" python3 launch.py %*
set "EXIT_CODE=%ERRORLEVEL%"
goto finish

:native

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

:finish
if not "%EXIT_CODE%"=="0" (
    echo.
    pause
)

exit /b %EXIT_CODE%
