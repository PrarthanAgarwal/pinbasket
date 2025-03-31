@echo off
echo PinBasket - Pinterest Image Collection Tool
echo ===========================================
echo.

rem Get search query from user
set /p QUERY="Enter search query: "

rem Get number of images (default: 10)
set /p IMG_COUNT="Number of images to download [10]: "
if "%IMG_COUNT%"=="" set IMG_COUNT=10

rem Get scroll count based on image count (higher for more images)
set /p SCROLL_COUNT="Number of scrolls [5]: "
if "%SCROLL_COUNT%"=="" (
    if %IMG_COUNT% LEQ 10 (
        set SCROLL_COUNT=3
    ) else if %IMG_COUNT% LEQ 30 (
        set SCROLL_COUNT=5
    ) else (
        set SCROLL_COUNT=8
    )
)

echo.
echo Running search for: "%QUERY%"
echo Will download up to %IMG_COUNT% images with %SCROLL_COUNT% scrolls
echo.

rem Check if credentials environment variables exist
if not defined PINTEREST_EMAIL (
    set /p PINTEREST_EMAIL="Enter Pinterest email (or press Enter to skip login): "
)

if not defined PINTEREST_PASSWORD (
    if not "%PINTEREST_EMAIL%"=="" (
        set /p PINTEREST_PASSWORD="Enter Pinterest password: "
    )
)

rem Build command based on whether credentials were provided
set CMD_BASE=python pinterest_img_scraper.py --query "%QUERY%" --timeout 90000 --visible --scroll %SCROLL_COUNT% --limit %IMG_COUNT% --min-width 500 --min-height 500

if not "%PINTEREST_EMAIL%"=="" (
    if not "%PINTEREST_PASSWORD%"=="" (
        set CMD=%CMD_BASE% --email "%PINTEREST_EMAIL%" --password "%PINTEREST_PASSWORD%"
    ) else (
        set CMD=%CMD_BASE%
    )
) else (
    set CMD=%CMD_BASE%
)

rem Run the command
%CMD%

echo.
echo Done! Press any key to exit...
pause > nul 