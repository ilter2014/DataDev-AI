@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Kume Yonetim Merkezi
py -3 -X utf8 datadev_cluster_app.py
if errorlevel 1 (
  echo.
  echo Uygulama hata ile kapandi. Python 3 ve baglanti ayarlarini kontrol et.
  pause
)
