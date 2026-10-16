@echo off
chcp 65001 >nul
cd /d "%~dp0"
python datadev_gpt_v2.py --chat
pause
