@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Worker
echo DataDev AI isci istemcisi
echo Once DATADEV_CLUSTER_URL ve DATADEV_CLUSTER_WORKER_TOKEN ortam degiskenlerini ayarla.
if "%DATADEV_CLUSTER_URL%"=="" (
  set /p DATADEV_CLUSTER_URL=Koordinator HTTPS adresi: 
)
if "%DATADEV_CLUSTER_WORKER_TOKEN%"=="" (
  echo Worker anahtari ortam degiskeninde tanimli degil.
  echo PowerShell'de once $env:DATADEV_CLUSTER_WORKER_TOKEN = "VDS'deki worker anahtari" yaz.
  pause
  exit /b 1
)
set /p WORKER_ID=Bu bilgisayarin isci kimligi (ilter-pc / mert-pc / vds-worker): 
if "%WORKER_ID%"=="" set WORKER_ID=ilter-pc
python -X utf8 datadev_cluster_worker.py --server "%DATADEV_CLUSTER_URL%" --worker-id "%WORKER_ID%"
pause
