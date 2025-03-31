@echo off
echo PinBasket - Virtual Environment Setup
echo =============================================
echo.
echo This script will set up a Python virtual environment and install all required dependencies.
echo.

rem Check if Python is installed
python --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in your PATH.
    echo Please install Python 3.8 or higher from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during installation.
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

echo Setting up virtual environment...

rem Create virtual environment if it doesn't exist
if not exist venv\ (
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create virtual environment. 
        echo Please ensure you have the venv module installed.
        echo You might need to run: pip install virtualenv
        echo.
        echo Press any key to exit...
        pause > nul
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages...
pip install -r requirements.txt

echo Installing Playwright browsers...
playwright install chromium

echo.
echo Virtual environment setup complete!
echo.
echo You can now run PinBasket using:
echo 1. Double-click on pinterest_search.bat to start scraping
echo 2. Run setup_credentials.bat to set up your Pinterest credentials (optional)
echo.
echo Press any key to exit...
pause > nul

rem Deactivate virtual environment
call deactivate 