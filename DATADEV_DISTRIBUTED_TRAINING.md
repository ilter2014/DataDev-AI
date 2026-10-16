# DataDev AI — 500K model ve Radmin VPN ile dağıtık eğitim

Bu prototip, Windows VDS + İlter PC + Mert PC arasında CPU eğitim görevlerini dağıtır. Üç cihaz tek bir RAM/CPU gibi davranmaz; her worker kendi eğitim parçasını işler, güncellemesini VDS'ye gönderir ve yönetici açıkça onaylayınca FedAvg ile birleştirilir.

**Güncel Windows kurulum adımları:** `CLUSTER_QUICKSTART_TR.md` dosyasını takip et. Eski Tailscale/HTTPS örneklerini kullanma; mevcut kurulum Radmin VPN arayüzüne özel bağlanacak şekilde düzenlenmiştir.

## Model
- Aktif eğitim mimarisi: `datadev_gpt_v5.py`, checkpoint `datadev_gpt_v5_model.pt`.
- Parametre sayısı mevcut vocabulary ile yaklaşık 497.490'dır; vocabulary değişince sayı da değişebilir.
- Önceki yerel eğitimde 1.200 adımda validation loss 4.677'den 2.342'ye indi. Bu yalnızca sonraki karakter tahmin kaybıdır; akıcı veya güvenilir sohbet becerisini kanıtlamaz.

## Güvenlik
- VDS'de `cluster_secrets.txt` iki ayrı rastgele anahtar tutar: ADMIN_TOKEN ve WORKER_TOKEN. Bu dosya GitHub'a eklenmez.
- Admin token yalnızca İlter'in yönetim uygulamasında; worker token yalnızca worker cihazlarında kullanılmalıdır. Mert'e admin token verilmez.
- Koordinatör sadece VDS'nin Radmin VPN IPv4 adresinde TCP 8765 dinler. Windows Firewall sadece İlter ve Mert'in Radmin IPv4 adreslerine izin verir.
- Genel IP'de port yönlendirme yapma; VDS sağlayıcı güvenlik duvarında 8765'i herkese açma. Radmin VPN dışından HTTP adresine erişim verme.
- Worker'lar keyfi komut çalıştırmaz; yalnızca sabit eğitim görevini işler.

## İlk test
1. Her cihazın Radmin IP'sini doğrula.
2. VDS'de `cluster_vds_setup.bat`, ardından yönetici olarak `cluster_vds_firewall_setup.bat` çalıştır.
3. VDS'de `cluster_vds_start.bat` ve ikinci pencerede `cluster_vds_worker_start.bat` aç.
4. İlter ve Mert cihazlarında `cluster_worker_setup.bat` ve `cluster_worker_start.bat` aç.
5. İlter PC'de `DataDev AI - Küme Yönetim Merkezi.bat` ile bağlantıyı kontrol et, 10–20 adımlık bir tur başlat.
6. Üç worker da bitirdikten sonra Round ID ile birleştirme yap. Doğrulama kaybı kötüleşirse mevcut checkpoint korunmalıdır.

12 saatlik oturuma ancak ilk küçük tur başarılı olduktan sonra geç. Windows uyku modunu kapat; worker pencerelerini açık bırak. Eğitim sırasında elektrik/internet kesilirse bitmemiş görevleri yeniden kontrol et.
