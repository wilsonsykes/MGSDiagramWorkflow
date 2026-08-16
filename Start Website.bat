@echo off
cd /d "%~dp0"
echo Starting the website...
echo.
echo Once you see "Accepting connections", open your browser to:
echo     http://localhost:3060
echo.
echo Keep this window open while you're using the site.
echo Close this window (or press Ctrl+C) to turn it off.
echo.
npx serve -l 3060 .
pause
