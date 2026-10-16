@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev GPT v5 - 500K Egitim
python -X utf8 datadev_gpt_v5.py --steps 1200
pause
