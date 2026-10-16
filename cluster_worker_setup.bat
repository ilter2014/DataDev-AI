@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev AI - Worker Kurulum
if not exist "datadev_cluster_worker.py" (
  echo HATA: Once DataDev-AI projesini indir ve bu dosyayi proje klasorune koy.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 (
    echo HATA: Python 3.11+ bulunamadi.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install torch
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m py_compile datadev_cluster_worker.py datadev_gpt_v5.py
if errorlevel 1 goto fail
echo.
echo Worker kurulumu tamam. Simdi cluster_worker_start.bat dosyasini calistir.
pause
exit /b 0
:fail
echo Worker kurulumu basarisiz. Python, internet ve disk alanini kontrol et.
pause
exit /b 1
