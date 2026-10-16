@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title DataDev AI - Sabah Testi
if not exist "datadev_gpt_v4.py" (
 echo HATA: datadev_gpt_v4.py bulunamadi.
 pause
 exit /b 1
)
if not exist "datadev_gece_egitimi_state.json" (
 echo UYARI: Gece egitimi durum dosyasi yok.
)
echo =====================================================
echo DATADEV AI - SABAH KONTROLU
echo =====================================================
echo Bu test dosyalari ve egitim kayitlarini kontrol eder.
echo Modeli yeniden egitmez ve mevcut modeli degistirmez.
echo.
python -c "import json, pathlib, datetime; p=pathlib.Path('.'); state=p/'datadev_gece_egitimi_state.json'; log=p/'datadev_gece_egitimi.log'; data=p/'datadev_curriculum_training.jsonl'; print('Saat:',datetime.datetime.now().astimezone().isoformat()); print('Model dosyasi:'); [print(' -',x.name, f'{x.stat().st_size:,} bayt', datetime.datetime.fromtimestamp(x.stat().st_mtime).astimezone().isoformat()) for x in p.glob('*.pt')]; print('Veri seti:', data.name, (f'{sum(1 for line in data.open(encoding=\"utf-8\") if line.strip())} satir' if data.exists() else 'YOK')); print('Durum:'); print(state.read_text(encoding='utf-8') if state.exists() else 'Durum dosyasi yok'); print('Son log satirlari:'); print(''.join(log.read_text(encoding='utf-8',errors='replace').splitlines(True)[-18:]) if log.exists() else 'Log yok')"
echo.
echo =====================================================
echo Bu yalnizca kayit kontroludur; dil ve bilgi testi icin modelin gercek sohbet arayuzunden ayrica sorular sorulmalidir.
echo =====================================================
pause
