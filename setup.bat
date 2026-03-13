@echo off
title ASX200 Setup
echo.
echo  ================================================
echo    ASX200 Report — First-Time Setup
echo  ================================================
echo.

:: ── Step 1: Find Python ──────────────────────────────────────────────────────
set PYTHON=

where py >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=py & goto :found_python )

where python >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=python & goto :found_python )

where python3 >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=python3 & goto :found_python )

echo  [ERROR] Python not found on this computer.
echo.
echo  Please install Python 3.10 or newer from:
echo    https://www.python.org/downloads/
echo.
echo  During installation, tick "Add Python to PATH".
echo  Then run this setup.bat again.
echo.
pause
exit /b 1

:found_python
echo  [OK] Found Python: %PYTHON%
%PYTHON% --version
echo.

:: ── Step 2: Check Python version (need 3.10+) ────────────────────────────────
%PYTHON% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARNING] Python 3.10 or newer is recommended.
    echo  Your version may still work, but consider upgrading.
    echo.
)

:: ── Step 3: Install required packages ────────────────────────────────────────
echo  Installing required packages...
echo  (This may take a minute on first run)
echo.
%PYTHON% -m pip install -r "%~dp0requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Package installation failed.
    echo  Try running this window as Administrator, or install manually:
    echo    pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo  [OK] All packages installed successfully.
echo.
echo  ================================================
echo    Setup complete! You can now run:
echo      launch_report.bat
echo  ================================================
echo.
pause
