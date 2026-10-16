@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev Hive - Worker

echo ================================================
echo          DataDev Hive - Isci Bilgisayar
echo ================================================
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo HATA: Python 3 bulunamadi.
    echo Python 3.10 veya yenisini kur: https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYTHON=python"
)
%PYTHON% --version
if errorlevel 1 (
  echo HATA: Python baslatilamadi.
  pause
  exit /b 1
)
echo.
echo DataDev Hive menusu aciliyor.
echo Rol seciminde 2 yaz.
echo Worker adi olarak ilter-pc veya mert-pc kullanin.
echo VDS adresi olarak Radmin VPN IP adresini ve :8765 portunu girin.
echo Token'i VDS ekranindan alip guvenli sekilde yapistirin.
echo.
%PYTHON% "%~dp0datadev_hive.py"
pause
