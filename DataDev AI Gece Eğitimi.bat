@echo off
chcp 65001 >nul
title DataDev AI - Gece Egitim Modu
cd /d "%~dp0"
echo.
echo ==========================================================
echo           DATADEV AI - GECE EGITIM MODU
echo ==========================================================
echo Groq tek tek ders hazirlayacak; hata olursa bekleyip deneyecek.
echo Groq yokken yerel kitap/makaleler islenecek.
echo Varsayilan: 6 saat ders toplama + tam yerel egitim.
echo Bilgisayari kapatmayin. Ekran kapanabilir; uyku engellenir.
echo Durdurmak icin bu pencerede CTRL+C kullanabilirsiniz.
echo.
python -u datadev_gece_egitimi.py --hours 6
echo.
echo Gece egitimi sonlandi. Kayit: datadev_gece_egitimi.log
pause
