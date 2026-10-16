@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -u datadev_konus.py
echo.
pause
