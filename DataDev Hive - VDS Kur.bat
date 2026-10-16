@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev Hive - VDS Görev Merkezi

echo ================================================
echo       DataDev Hive - VDS Kurulum / Baslatma
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

echo [1/3] Python kontrol ediliyor...
%PYTHON% --version
if errorlevel 1 (
  echo HATA: Python baslatilamadi.
  pause
  exit /b 1
)

echo.
echo [2/3] Radmin VPN erisim kuralini eklemeyi deniyorum.
echo Bu adim yonetici yetkisi ister; hata olursa PowerShell'i yonetici olarak ac.
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-NetFirewallRule -DisplayName 'DataDev Hive Radmin VPN 8765' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'DataDev Hive Radmin VPN 8765' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -RemoteAddress 26.0.0.0/8 -Profile Any | Out-Null }; Write-Output 'Windows Firewall kurali kontrol edildi.'" 2>nul

echo.
echo [3/3] Gorev merkezi aciliyor.
echo Rol seciminde 1 yaz, port sorusunda Enter'a bas (8765).
echo Yalnizca VPN uzerinden baglanin; token'i herkese acik kanalda paylasmayin.
echo.
%PYTHON% "%~dp0datadev_hive.py"
if errorlevel 1 echo DataDev Hive kapandi veya hata verdi.
pause
