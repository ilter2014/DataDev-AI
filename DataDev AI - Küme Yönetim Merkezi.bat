@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Kume Yonetim Merkezi
python -X utf8 datadev_cluster_app.py
if errorlevel 1 (
  echo.
  echo Uygulama hata ile kapandi. Python kurulumunu ve baglanti ayarlarini kontrol et.
  pause
)
