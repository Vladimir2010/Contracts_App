@echo off
echo ========================================================
echo   Contracts App - Server Configuration
echo   Unblocking Port 8000 (Force Public/Private)...
echo ========================================================
echo.

:: Check for permissions
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Success: Running with Administrator privileges.
) else (
    echo ERROR: You must right-click this file and select "Run as Administrator"
    echo.
    pause
    exit
)

echo.
echo 1. Removing old rules (if any)...
netsh advfirewall firewall delete rule name="ContractsApp Sync"

echo.
echo 2. Adding NEW Rule (Allowed on Public & Private)...
netsh advfirewall firewall add rule name="ContractsApp Sync" dir=in action=allow protocol=TCP localport=8000 profile=any

echo.
echo ========================================================
echo   DONE! Port 8000 is open for ALL networks.
echo   You should be able to connect even on Public Wi-Fi.
echo ========================================================
echo.
pause
