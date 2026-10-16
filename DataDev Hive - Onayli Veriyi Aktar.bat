@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev Hive - Onayli Veri Aktarimi
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0datadev_hive_sync.py"
) else (
  python "%~dp0datadev_hive_sync.py"
)
pause
