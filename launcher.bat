@echo off
rem Trainer Hub launcher - uses the bundled Python in .\runtime (no install needed).
rem   launcher.bat         start normally (no console window)
rem   launcher.bat debug   start with a console to see errors
cd /d "%~dp0"

if not exist "runtime\pythonw.exe" goto noruntime

if /i "%~1"=="debug" (
    "runtime\python.exe" -m app.main
    pause
    exit /b
)
start "" "runtime\pythonw.exe" -m app.main
exit /b

:noruntime
echo The bundled Python runtime (runtime\) was not found.
echo.
echo  - Users: download the release zip from GitHub Releases, it already includes runtime\.
echo  - Developers: build it once with an installed Python 3.11+:
echo        python tools\build_runtime.py
echo.
pause
