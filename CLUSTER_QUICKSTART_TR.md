# DataDev AI — 3 cihazli dagitik egitim (Windows)

## Yedek ve model

- GitHub deposu: https://github.com/ilter2014/DataDev-AI
- Model: `datadev_gpt_v5_model.pt`
- Modelin benzersiz parametre sayisi: 497,490 (137 karakterlik mevcut kelime dagarcigiyla). Checkpoint state-dict tensor toplami tied embedding nedeniyle daha yuksek gorunebilir.
- Bu sistem CPU islerini dagitir; uc bilgisayari tek bir RAM/CPU gibi birlestirmez.
- Aday model, tum isler bitince yonetici tarafindan birlestirilir. Dogrulama kaybi kotulesirse aktif model korunur.

## 1. VDS (Windows Server 2022)

1. Git kuruluysa: `git clone https://github.com/ilter2014/DataDev-AI.git DataDevAI`
2. Proje klasorunde `cluster_vds_setup.bat` dosyasini calistir. Python sanal ortami, PyTorch ve iki rastgele anahtar hazirlanir.
3. `cluster_secrets.txt` dosyasini VDS'de gizli tut. GitHub'a yukleme. Admin anahtari yalnizca yonetici PC'de; worker anahtari worker bilgisayarlarda kullanilir.
4. Tailscale'i VDS, Ilter PC ve Mert PC'ye kur; ucunu ayni ozel tailnet'e kat.
5. `cluster_vds_start.bat` calistir. Koordinator yalnizca `127.0.0.1:8765` uzerinde dinler.
6. VDS'de Tailscale Serve HTTPS kurulumunu tamamla; kurulu surumun yardimini kontrol et. Public HTTP veya public 8765 portu kullanma.
7. VDS'de ikinci terminalde `cluster_vds_worker_start.bat` calistir. Bu worker, ayni makinedeki koordinatora baglanir.

## 2. Ilter PC ve Mert PC

Her bilgisayarda:
1. Projeyi GitHub'dan klonla (Mert'in private depoya erisimi yoksa projeyi guvenli yoldan ZIP olarak aktar).
2. Proje klasorunde `cluster_worker_setup.bat` calistir.
3. `cluster_worker_start.bat` calistir.
4. Koordinatorun Tailscale HTTPS adresini yaz.
5. Worker kimligini gir: kendi PC'n icin `ilter-pc`, Mert icin `mert-pc`.
6. VDS'deki `DATADEV_CLUSTER_WORKER_TOKEN` degerini gizli token istemine gir. Bu pencereyi egitim boyunca acik tut.

## 3. Yonetici (Ilter PC)

- VDS'deki `DATADEV_CLUSTER_ADMIN_TOKEN` degerini yonetici uygulamasinin gizli anahtar istemine gir.
- `DataDev AI - Kume Yonetim Merkezi.bat` dosyasini calistir.
- Secenek 1: baglanti/durum.
- Secenek 2: yeni tur; ilk denemede her worker icin 10–20 adim onerilir.
- Uc worker da bitince Secenek 3 ile Round ID'yi birlestir.
- Sonuc baseline/candidate validation loss ile raporlanir. Daha kotu adaysa aktif checkpoint degistirilmez.

## 4. 12 saatlik calisma

- Her worker penceresini acik birak. Windows uyku/hibernation kapali olmali; elektrik ve internet kesilmemeli.
- Ilk turu kucuk adimla test et. 12 saat boyunca ayni turu tekrar tekrar otomatik olusturma; once her turu incele ve dogrula.
- Model birlestirme yonetici onayi gerektirir; worker PC'leri kendi basina rastgele komut calistirmaz.

## Guvenlik

- `cluster_secrets.txt` ve `.venv/` GitHub'a yuklenmez; `.gitignore` tarafindan dislanir.
- Admin token sadece yonetici uygulamasinda; worker token sadece worker istemcilerinde.
- Token'lari sohbetlere, ekran goruntulerine veya herkese acik yerlere koyma.
- Koordinator portu 8765'i internete acma; uzak baglanti icin Tailscale HTTPS/ozel ag kullan.
- Bu ilk prototip CPU tabanli FedAvg'dir. Model kalitesi sadece parametre sayisiyla olculmez.
