@echo off
echo PinBasket - Credentials Setup
echo =============================================
echo.
echo This script will help you set up your Pinterest credentials as environment variables.
echo Your credentials will be stored securely and won't be included in the repository.
echo.

set /p PINTEREST_EMAIL="Enter your Pinterest email: "
set /p PINTEREST_PASSWORD="Enter your Pinterest password: "

echo.
echo Setting up environment variables...

:: Create a batch file to set these variables each time
echo @echo off > set_pinterest_env.bat
echo echo Setting Pinterest credentials... >> set_pinterest_env.bat
echo setx PINTEREST_EMAIL "%PINTEREST_EMAIL%" >> set_pinterest_env.bat
echo setx PINTEREST_PASSWORD "%PINTEREST_PASSWORD%" >> set_pinterest_env.bat
echo echo Done! >> set_pinterest_env.bat

:: Run the created batch file to set environment variables
call set_pinterest_env.bat

echo.
echo Credentials have been set up!
echo To use PinBasket with these credentials, run pinterest_search.bat
echo.
echo Press any key to exit...
pause > nul 