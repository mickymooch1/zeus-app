@echo off
echo.
echo   ⚡ Zeus Backend
echo   Listening on http://0.0.0.0:8000
echo   Phone (same WiFi): http://192.168.0.17:8000
echo.
cd /d "%~dp0backend"
python main.py
