@echo off
chcp 65001 >nul
cd /d "%~dp0"
python datadev_gpt_v3.py --chat
pause
