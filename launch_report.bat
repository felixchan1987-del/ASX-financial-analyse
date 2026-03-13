@echo off
title ASX200 Report Server
echo.
echo  ================================================
echo    ASX200 Valuation Report Server
echo    Opening http://localhost:8765 in your browser
echo    Close this window to stop the server
echo  ================================================
echo.

:: Try py launcher first (Windows Python Launcher, most portable)
where py >nul 2>&1
if %errorlevel% == 0 (
    py "%~dp0server.py"
    goto :end
)

:: Fall back to python
where python >nul 2>&1
if %errorlevel% == 0 (
    python "%~dp0server.py"
    goto :end
)

:: Fall back to python3
where python3 >nul 2>&1
if %errorlevel% == 0 (
    python3 "%~dp0server.py"
    goto :end
)

echo ERROR: Python not found. Please run setup.bat first.
pause
:end
