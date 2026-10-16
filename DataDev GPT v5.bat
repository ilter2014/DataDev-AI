@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev GPT v5
python -X utf8 datadev_gpt_v5.py --chat
pause
