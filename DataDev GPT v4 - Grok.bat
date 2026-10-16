@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Yerel Model + Groq Geri Bildirim Dongusu
python datadev_gpt_loop.py
echo.
pause
