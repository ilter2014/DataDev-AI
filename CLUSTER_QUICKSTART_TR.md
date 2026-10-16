# DataDev AI — 500K model ve 3 cihazlı eğitim (Windows)

## GitHub yedeği
- Özel depo: https://github.com/ilter2014/DataDevAI-Git
- İlk tam proje yedeği: `backup/full-project-20261016` dalı
- Güncel Radmin VPN kurulumu ve betikler: `backup/radmin-cluster-20261016` dalı
- Model: `datadev_gpt_v5_model.pt`; yaklaşık 497.490 parametre (vocabulary değişirse sayı değişebilir).
- Bu sistem görevleri üç bilgisayara dağıtır; bilgisayarları tek bir RAM/CPU gibi birleştirmez. Sonuçlar merkezde doğrulanır.

## Ağ kararı: Radmin VPN
Üç cihazda da Radmin VPN kurulu olmalı ve aynı özel Radmin ağına katılmalılar. Radmin IPv4 adresini `ipconfig` ile bul; genellikle `26.x.x.x` biçimindedir. Ağ adı/parolasını herkese açık paylaşma.

**Koordinatör portunu VDS'nin genel IP'sine açma.** Sunucu yalnızca VDS'nin Radmin IPv4 adresine bağlanır; Windows Firewall kuralı yalnızca İlter ve Mert'in Radmin IP'lerine TCP 8765 izni verir. Radmin VPN üzerinden HTTP kullanılabilir; bu adresi VPN dışından kullanma.

## 1. VDS (Windows Server 2022)
1. VDS'ye Radmin VPN kur ve aynı özel ağa katıl.
2. Git yüklü ve private depoya erişimin varsa CMD'de çalıştır:
   ```bat
   git clone --branch backup/radmin-cluster-20261016 https://github.com/ilter2014/DataDevAI-Git.git DataDevAI
   ```
   VDS'de GitHub erişimi yoksa İlter PC'deki `DataDevAI-VDS-Kurulum.zip` dosyasını VDS'ye kopyalayıp `DataDevAI` klasörüne çıkar.
3. `cluster_vds_setup.bat` çalıştır; Python ve PyTorch CPU kurulur, gizli anahtarlar oluşturulur.
4. `cluster_vds_firewall_setup.bat` dosyasına sağ tıklayıp **Yönetici olarak çalıştır**. VDS'nin Radmin IPv4 adresini ve İlter/Mert'in Radmin IPv4 adreslerini gir.
5. `cluster_vds_start.bat` çalıştır ve aynı VDS Radmin IP'sini gir. Koordinatör o adrese TCP 8765 üzerinde bağlanır.
6. İkinci terminalde `cluster_vds_worker_start.bat` çalıştır, aynı Radmin IP'sini gir.

## 2. İlter PC ve Mert PC
Her bilgisayarda:
1. Radmin VPN'i aç; aynı özel ağa katıl. `ipconfig` ile kendi Radmin IP'ni öğren.
2. İlter kendi PC'sinde güncel proje klasörünü kullanır. Mert'in özel depoya erişimi yoksa `Mert-Worker-Paketi.zip` dosyasını gönder.
3. `cluster_worker_setup.bat` çalıştır.
4. `cluster_worker_start.bat` çalıştır.
5. VDS Radmin adresini `http://VDS_RADMIN_IP:8765` biçiminde gir; worker kimliği olarak İlter için `ilter-pc`, Mert için `mert-pc` seç.
6. VDS'deki `cluster_secrets.txt` dosyasından yalnızca WORKER_TOKEN değerini güvenli biçimde gir. Admin token'ı Mert'e gönderme.

## 3. Eğitim turunu başlatma
1. İlter PC'de `DataDev AI - Küme Yönetim Merkezi.bat` çalıştır.
2. VDS Radmin URL'sini ve ADMIN_TOKEN'ı gir.
3. Önce [1] ile bağlantıyı doğrula.
4. [2] ile küçük bir tur oluştur; ilk test için işçi başına 10–20 adım seç.
5. Üç worker da sonuçlarını VDS'ye gönderene kadar bekle.
6. Round ID'yi sakla; [3] ile sonuçları birleştir ve validation kontrolünü çalıştır. Loss kötüleşirse mevcut model korunur.

## 12 saat açık bırakmadan önce
- İlk önce 1 küçük turu baştan sona test et; başarı görülmeden 12 saatlik oturum başlatma.
- Bilgisayarların uyku modunu kapat; internet ve elektrik kesilmemeli.
- Her worker penceresini açık tut. Durdurmak için Ctrl+C.
- Görevler ve sonuçlar VDS'de `datadev_cluster` altında tutulur. Eğitim kayıtlarını ve model sürümlerini düzenli yedekle.

## Güvenlik ve teknik sınırlar
- `cluster_secrets.txt`, API anahtarları, tokenlar ve yerel .env dosyaları GitHub'a yüklenmez.
- Worker'lar rastgele komut çalıştırmaz; yalnızca sabit eğitim kodunu çalıştırır.
- Radmin VPN ağı dışından `http://26.x.x.x:8765` kullanma. Genel IP'de port yönlendirme yapma.
- Bu ilk sürüm CPU tabanlı FedAvg prototipidir. Parametre sayısı tek başına modelin zekâsını göstermez.
