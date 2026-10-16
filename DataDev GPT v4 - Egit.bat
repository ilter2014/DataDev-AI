@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DataDev GPT v4 - Onayli Verilerle Egitim
echo.
echo Onayladigin /duzelt ile verdigin cevaplar datadev_user_learning.jsonl dosyasindan egitime eklenecek.
echo Bu islem modeli bastan egitir; mevcut model once yedeklenecek.
echo.
if exist "datadev_gpt_v4_model.pt" copy /y "datadev_gpt_v4_model.pt" "datadev_gpt_v4_model.before_retrain.bak" >nul
python datadev_gpt_v4.py
echo.
pause
