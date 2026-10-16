@echo off
setlocal
title DataDev AI - Gece Egitimi
chcp 65001 >nul
cd /d "%~dp0"

if not exist "datadev_gece_egitimi.py" (
  echo HATA: datadev_gece_egitimi.py bu klasorde bulunamadi.
  echo Bu BAT dosyasini DataDevAI klasorune kopyalayip oradan calistir.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo HATA: Python PATH icinde bulunamadi. Python kurulumunu kontrol et.
  pause
  exit /b 1
)

echo =====================================================
echo   DATADEV AI - GECE EGITIMI
echo =====================================================
echo Groq dersleri + yerel kaynaklar + yerel model egitimi
echo Log: datadev_gece_egitimi.log
echo Durum: datadev_gece_egitimi_state.json
echo Bilgisayarin uykuya gecmesini engelle; bu pencereyi kapatma.
echo Baslangic: %date% %time%
echo.

python -u datadev_gece_egitimi.py --hours 6
set "RC=%ERRORLEVEL%"

echo.
echo =====================================================
echo Egitim sureci sonlandi. Cikis kodu: %RC%
echo Sonuclari datadev_gece_egitimi.log ve datadev_gece_egitimi_state.json dosyalarindan kontrol et.
echo Bu BAT tek basina grafik paneli eklemez; grafik icin egitim gunluklerinden veri okunmasi gerekir.
echo =====================================================
pause
exit /b %RC%
