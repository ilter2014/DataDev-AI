DATADEV AI 0.1
==============

Bu klasordeki ana program datadev_ai.py dosyasidir.
Model hazir bir yapay zeka servisi kullanmadan NumPy ile sifirdan egitilir.

Kurulum:
  python -m pip install numpy

Calistirma:
  python datadev_ai.py

Kendi verilerin:
  Bu klasorde UTF-8 kodlamasiyla data.txt dosyasi olustur ve egitim metinlerini ekle.
  Program bu metinleri baslangic ornekleriyle birlestirerek egitim yapar.

Olusan model dosyalari:
  datadev_ai_model.npz
  datadev_ai_vocab.json

Bu, karakter oruntulerini ogrenmeye calisan kucuk bir prototiptir. Genel bilgiye sahip
degildir ve dogru cevaplar veya akici Turkce garanti etmez.
