@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev AI - Radmin Koordinator
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
echo.
echo VDS Radmin VPN IPv4 adresini ipconfig komutundan bul.
echo Ornek: 26.x.x.x  ^(ornek adresi kopyalama, kendi VDS adresini gir^)
set /p "RADMIN_IP=VDS Radmin IPv4: "
if "%RADMIN_IP:~0,3%" NEQ "26." (
  echo HATA: Radmin VPN adresi 26.x.x.x biciminde olmali.
  pause
  exit /b 1
)
echo.
echo Koordinator yalnizca %RADMIN_IP%:8765 adresinde dinleyecek.
echo Public IP veya 0.0.0.0 kullanilmiyor. Firewall izinlerini ayri ayarla.
".venv\Scripts\python.exe" -X utf8 datadev_cluster_server.py --host %RADMIN_IP% --port 8765
pause
exit /b 0
:secrets_error
echo cluster_secrets.txt icindeki anahtarlar eksik veya bozuk.
pause
exit /b 1
