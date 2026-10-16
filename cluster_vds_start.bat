@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev AI - Koordinator
if not exist ".venv\Scripts\python.exe" (
  echo Once cluster_vds_setup.bat dosyasini calistir.
  pause
  exit /b 1
)
if not exist "cluster_secrets.txt" (
  echo cluster_secrets.txt bulunamadi. Once cluster_vds_setup.bat dosyasini calistir.
  pause
  exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in ("cluster_secrets.txt") do set "%%A=%%B"
if "%DATADEV_CLUSTER_ADMIN_TOKEN%"=="" goto secrets_error
if "%DATADEV_CLUSTER_WORKER_TOKEN%"=="" goto secrets_error
echo Koordinator localhost:8765 uzerinde aciliyor.
echo Uzak baglanti icin Tailscale Serve/HTTPS gerekir. Port 8765'i internete acma.
".venv\Scripts\python.exe" -X utf8 datadev_cluster_server.py --host 127.0.0.1 --port 8765
pause
exit /b 0
:secrets_error
echo cluster_secrets.txt icindeki anahtarlar eksik veya bozuk.
pause
exit /b 1
