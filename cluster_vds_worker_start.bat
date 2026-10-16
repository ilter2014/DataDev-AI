@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev AI - VDS Worker
if not exist ".venv\Scripts\python.exe" (
  echo Once cluster_vds_setup.bat dosyasini calistir.
  pause
  exit /b 1
)
if not exist "cluster_secrets.txt" (
  echo cluster_secrets.txt bulunamadi.
  pause
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in ("cluster_secrets.txt") do set "%%A=%%B"
if "%DATADEV_CLUSTER_WORKER_TOKEN%"=="" (
  echo Worker token bulunamadi.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 datadev_cluster_worker.py --server http://127.0.0.1:8765 --worker-id vds-worker
pause
