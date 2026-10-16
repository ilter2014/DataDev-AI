# DataDev Hive — 3 bilgisayarlı görev ağı

## Amaç ve mevcut sınır

- **VDS:** merkezi görev/veri bankası; worker'lara incelenecek kayıtları dağıtır.
- **İlter PC ve Mert PC:** görevleri alır, kayıtların metinsel kalite analizini yapar ve analiz sonuçlarını VDS'ye yollar.
- **İlter PC:** insan tarafından onaylanan veriyi indirir ve DataDev GPT v5 modelini yerel olarak eğitir.
- **Model:** v5 yaklaşık 497.490 parametreli, karakter tabanlı küçük bir prototiptir.

Önemli: Bu sürüm üç bilgisayar arasında PyTorch gradyanlarını dağıtmaz ve parametreleri doğrudan birleştirmez. Dağıtık olan kısım görev kuyruğu, kayıt analizi ve onaylı veri aktarımıdır; nihai model eğitimi İlter PC'de yapılır. Farklı bilgisayarlarda bağımsız checkpoint'leri gelişigüzel ortalamak model kalitesini bozabileceği için yapılmıyor.

## 1. VDS kurulumu

1. VDS'ye Python 3.10+ kurulu olsun.
2. datadev_hive.py ve DataDev Hive - VDS Kur.bat dosyalarını aynı klasöre koy.
3. DataDev Hive - VDS Kur.bat dosyasını çalıştır.
4. Menüde rol olarak 1 seç; port sorusunda Enter'a basarak 8765 kullan.
5. Konsolda üretilen token'i güvenli bir kanaldan İlter'e ve Mert'e ilet. Token'i GitHub'a, herkese açık sohbete veya ekran görüntüsüne koyma.
6. VDS'de Radmin VPN kurulu ve ağa bağlı olsun. Worker'lar VDS'nin **Radmin VPN IP** adresini kullanmalı; genel internet IP'sini kullanmayın.

Kurulum BAT'i Windows Firewall'da TCP 8765 için 26.0.0.0/8 kaynak aralığıyla kural eklemeyi dener. Başarısız olursa PowerShell'i yönetici olarak açıp aynı kuralı eklemek gerekir. Sağlayıcının VDS firewall panelinde de gerekirse izin verin. Portu tüm internete açmayın.

## 2. Veri bankasını doldurma

1. İlter PC'de DataDev Hive - Worker.bat çalıştır.
2. Menüde 2 (Worker) seç.
3. Worker adı ilter-pc; VDS adresi http://VDS_RADMIN_IP:8765; VDS token'ini gir.
4. Worker menüsünde 3 — Yerel JSONL dosyasından aktar seçip datadev_master_dataset.jsonl dosyasını gönder.
5. Yalnızca güvenilir ve izinli kaynaklardan gelen, eğitimde kullanma hakkınız olan verileri aktarın.

Her worker VDS'deki analiz edilmemiş kayıtları alır ve kalite puanı/öneri üretir. Worker ekranında görev kalmadığında bekleme mesajı görülür.

## 3. Mert'in bilgisayarı

1. Mert'e Mert-Worker-Paketi.zip dosyasını gönder.
2. ZIP'i çıkarsın; DataDev Hive - Worker.bat dosyasını açsın.
3. Menüde 2 seçsin; worker adı mert-pc olsun.
4. VDS'nin Radmin VPN IP'si, 8765 portu ve token'i girilsin.
5. Görev kuyruğu bittiğinde worker beklemede kalabilir. Durdurmak için CTRL+C.

## 4. İnsan onayı ve model eğitimi

1. VDS menüsünde 1 ile kayıt/analiz istatistiklerini kontrol et.
2. 3 ile kaydı ara; 4 ile **yalnızca doğru ve kaliteli bulduğun** kaydı ID'siyle onayla.
3. İlter PC'de DataDev Hive - Onayli Veriyi Aktar.bat çalıştır; aynı VDS URL/token bilgilerini gir.
4. Program yalnızca approved: true kayıtlarını datadev_hive_import.jsonl dosyasına indirir. Mevcut aktarım dosyası değişecekse önce .bak yedeği alınır.
5. İlter PC'de DataDev GPT v5 - Egit.bat çalıştır. datadev_gpt_v5.py, yalnızca onaylı Hive aktarımını da eğitim örneklerine ekler.
6. datadev_gpt_v5_training_report.py / benchmark ile loss ve örnek cevapları kontrol et. Düşük loss tek başına iyi cevap garantisi değildir.

## 5. 12 saatlik çalışma öncesi kontrol listesi

- [ ] VDS, İlter PC ve Mert PC aynı Radmin VPN ağına bağlı.
- [ ] Her worker /api/status ile bağlanabiliyor ve VDS'de node olarak görünüyor.
- [ ] Worker'lar kayıt alıp sonuç gönderebiliyor.
- [ ] approved olmayan kayıtlar eğitim aktarımına girmiyor.
- [ ] Model ve veri kümesinin yedeği alındı.
- [ ] Windows uyku/hibernation ayarları çalışma süresince uygun.
- [ ] VDS token'i yalnızca güvenilir cihazlarda saklanıyor.

Önce kısa bir 5–10 dakikalık test yapın; tüm cihazlar bağlanıp veri dönmeden 12 saatlik oturum başlatmayın.
