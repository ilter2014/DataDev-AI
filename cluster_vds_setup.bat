@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title DataDev AI - VDS Hazirlik
echo ============================================
echo DATADEV AI - VDS KURULUM HAZIRLAYICISI
echo ============================================
if not exist "datadev_cluster_server.py" (
  echo HATA: Proje klasorunde calistir.
  pause
  exit /b 1
)
if not exist "datadev_gpt_v5_model.pt" (
  echo HATA: datadev_gpt_v5_model.pt bulunamadi. Model olmadan devam edilmiyor.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 (
    echo HATA: Python 3.11+ bulunamadi. Python 3.11 veya 3.13 kurup tekrar dene.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install torch
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import torch,datadev_gpt_v5 as m; a,b,*_=m.build_corpus(); chars=sorted(set(a+b)); print('PyTorch:',torch.__version__); print('Vocab:',len(chars)); print('Model parametre:',sum(p.numel() for p in m.TinyGPT(len(chars)).parameters()))"
if errorlevel 1 goto fail
if not exist "cluster_secrets.txt" (
  ".venv\Scripts\python.exe" -c "import secrets,pathlib; p=pathlib.Path('cluster_secrets.txt'); p.write_text('DATADEV_CLUSTER_ADMIN_TOKEN='+secrets.token_urlsafe(48)+'\nDATADEV_CLUSTER_WORKER_TOKEN='+secrets.token_urlsafe(48)+'\n',encoding='utf-8')"
  if errorlevel 1 goto fail
  echo.
  echo Iki guclu anahtar olusturuldu: cluster_secrets.txt
  echo Bu dosyayi GitHub'a yukleme veya herkese gonderme.
) else (
  echo Mevcut cluster_secrets.txt korundu; anahtarlar yenilenmedi.
)
echo.
echo KURULUM TAMAM.
echo 1. cluster_secrets.txt dosyasini guvenli tut.
echo 2. ADMIN_TOKEN yalnizca yonetici PC'de kullanilacak.
echo 3. WORKER_TOKEN Ilter, Mert ve VDS worker icin kullanilacak.
echo 4. Radmin VPN'i uc cihaza kurup ayni ozel Radmin agina katil.
echo 5. Once cluster_vds_firewall_setup.bat dosyasini YONETICI olarak calistir.
echo 6. VDS'de cluster_vds_start.bat dosyasini calistir.
notepad cluster_secrets.txt
pause
exit /b 0
:fail
echo.
echo HATA: Kurulum basarisiz. Internet/Python/PyTorch kurulumunu kontrol et.
pause
exit /b 1
