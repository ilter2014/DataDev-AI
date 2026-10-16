@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Worker
if not exist "cluster_worker_start.ps1" (
  echo cluster_worker_start.ps1 bulunamadi.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cluster_worker_start.ps1"
pause
