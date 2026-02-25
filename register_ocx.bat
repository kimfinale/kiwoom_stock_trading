@echo off
echo Registering Kiwoom Open API OCX...
echo Note: This script may need Administrator privileges.

regsvr32 /s C:\OpenAPI\khopenapi.ocx

if %ERRORLEVEL% EQU 0 (
    echo ✅ Registration Successful.
) else (
    echo ❌ Registration Failed with error code %ERRORLEVEL%.
    echo    Try running this script as Administrator.
)
pause
