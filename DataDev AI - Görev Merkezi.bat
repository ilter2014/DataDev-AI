@echo off
chcp 65001 >nul
cd /d "%~dp0"
python datadev_task_manager.py
pause
