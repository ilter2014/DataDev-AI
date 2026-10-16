@echo off
chcp 65001 >nul
title DataDev AI - Groq Kontrol Paneli
cd /d "%~dp0"
if not exist "%~dp0DataDev AI Groq Paneli.ps1" (
  echo HATA: DataDev AI Groq Paneli.ps1 bulunamadi.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0DataDev AI Groq Paneli.ps1"
