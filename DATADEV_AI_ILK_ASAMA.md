DATADEV AI — İLK AŞAMA DURUMU
==============================

HAZIRLANAN
- datadev_api.py: yerel JSON API prototipi.
- DataDev AI API.bat: API'yi başlatma kısayolu.
- /health: servis ve model dosyası kontrolü.
- POST /v1/chat: soru alıp yerel kaynaklardan cevap oluşturma; Groq anahtarı varsa cevap denetimi.
- Girdi boyutu kontrolü, boş soru reddi, basit istek sınırı.
- Varsayılan olarak yalnızca 127.0.0.1 üzerinde dinleme.
- Dış arayüzde başlatmak için DATADEV_API_TOKEN zorunluluğu.
- VDS_KONTROL.ps1: VDS donanım/yazılım bilgilerini salt okunur toplar.

TEST
- Python sözdizimi kontrolü geçti.
- /health yanıtı başarılı.
- /v1/chat yanıtı başarılı (yerel kaynak cevabı).
- Boş soru 400 ile reddedildi.
- Harici IP üzerinde güvenli token kuralı için kod yolu kontrol edildi.

HENÜZ YAPILMADI
- VDS'ye kurulum/deploy: Bu oturumda VDS cihazına erişim yok; yalnızca geliştirme bilgisayarı bağlı.
- Gerçek Groq API testi: groq_api_key.txt boş/anahtar ayarlanmamış; anahtarı sohbetten gönderme.
- Kullanıcı hesapları, kimlik doğrulama ve kalıcı kotalar.
- Kullanıcının kendi Groq API anahtarını güvenli saklama.
- Web/Android/Windows arayüzleri.
- Katkı cihazları ve kota karşılığı hesaplama.
- Eğitim örneklerinin izinli toplanması, filtrelenmesi ve yeniden eğitim.
- HTTPS, reverse proxy, izleme, yedekleme ve üretim güvenlik denetimi.

ÖNEMLİ
Bu prototipi doğrudan internete açma. Üretim yayını için hesap/oturum sistemi, kalıcı kota, HTTPS,
güvenli anahtar saklama, izleme ve yük testleri tamamlanmalı. Mevcut yerel bilgisayarda 8 GB RAM'in
yaklaşık 1.4 GB'ı boş ve CUDA görünmüyor; bu yüzden burada eğitim çalıştırmadık.
