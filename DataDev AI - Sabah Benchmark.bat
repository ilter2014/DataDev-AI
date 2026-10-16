@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Sabah Benchmark
if not exist "datadev_benchmark.py" (
  echo HATA: datadev_benchmark.py bulunamadi.
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo HATA: Python PATH icinde bulunamadi.
  pause
  exit /b 1
)
python -u datadev_benchmark.py
echo.
echo Test bitti. datadev_benchmark_report.txt dosyasini ac.
pause
