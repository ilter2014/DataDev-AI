@echo off
chcp 65001 >nul
title DataDev AI - Radmin Firewall Kurulumu
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cluster_vds_firewall_setup.ps1"
if errorlevel 1 echo Firewall kurulumu basarisiz. Bu dosyayi VDS'de YONETICI olarak calistir.
pause
