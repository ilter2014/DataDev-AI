# -*- coding: utf-8 -*-
"""İndirir: Türkiye'de telif süresi dolmuş klasik eserleri Vikikaynak API'sinden.
Kaynak metinleri ayrı kitaplar/ klasörüne koyar; eğitim betiği bu dosyaları kullanabilir.
"""
from pathlib import Path
import json, re, time, urllib.parse, urllib.request

BASE = Path(__file__).resolve().parent
OUT = BASE / "kitaplar"
OUT.mkdir(exist_ok=True)
API = "https://tr.wikisource.org/w/api.php"
HEADERS = {"User-Agent": "DataDevAI-Local-Educational-Project/1.0 (public-domain text download)"}
# Yazarları Türkiye'de 70 yıllık koruma süresi dolmuş klasik eserler.
WORKS = [
    ("İntibah", "Namık Kemal", 1888),
    ("Araba Sevdası", "Recaizade Mahmut Ekrem", 1914),
    ("Felatun Bey ile Rakım Efendi", "Ahmet Mithat Efendi", 1912),
    ("Sergüzeşt", "Samipaşazade Sezai", 1936),
    ("Eylül", "Mehmet Rauf", 1931),
    ("Mai ve Siyah", "Halit Ziya Uşaklıgil", 1945),
    ("Aşk-ı Memnu", "Halit Ziya Uşaklıgil", 1945),
    ("Kuyruklu Yıldız Altında Bir İzdivaç", "Hüseyin Rahmi Gürpınar", 1944),
    ("Şıpsevdi", "Hüseyin Rahmi Gürpınar", 1944),
    ("Türkçülüğün Esasları", "Ziya Gökalp", 1924),
    ("Kaşağı", "Ömer Seyfettin", 1920),
    ("Pembe İncili Kaftan", "Ömer Seyfettin", 1920),
]

def api(params):
    url = API + "?" + urllib.parse.urlencode({"format": "json", **params})
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def norm(s):
    return re.sub(r"[^a-z0-9çğıöşü]", "", s.casefold().replace("ı", "i"))

manifest = []
for title, author, death_year in WORKS:
    try:
        found = api({"action":"query", "list":"search", "srsearch":title, "srnamespace":0, "srlimit":10})
        results = found.get("query", {}).get("search", [])
        if not results:
            print(f"YOK: {title} — Vikikaynak aramasında bulunamadı.")
            continue
        exact = [x for x in results if norm(x["title"]) == norm(title)]
        flat = [x for x in results if "/" not in x["title"]]
        chosen = (exact or flat or results)[0]
        page = api({"action":"query", "prop":"extracts|categories", "explaintext":1, "exsectionformat":"plain",
                    "cllimit":100, "pageids":chosen["pageid"]})
        item = next(iter(page.get("query", {}).get("pages", {}).values()))
        text = item.get("extract", "").strip()
        # Don't save stubs, indexes, or pages that aren't substantial book text.
        if len(text) < 7000:
            print(f"PAS GEÇ: {title} — bulunan sayfa yalnızca {len(text)} karakter.")
            continue
        safe = re.sub(r'[<>:"/\\|?*]', "_", title).replace(" ", "_")
        outpath = OUT / f"{safe}.txt"
        header = (f"{title}\nYazar: {author}\nYazarın ölüm yılı: {death_year}\n"
                  f"Kaynak: https://tr.wikisource.org/wiki/{urllib.parse.quote(chosen['title'].replace(' ', '_'))}\n"
                  "Not: Eser, Türkiye'deki genel yaşam + 70 yıl koruma süresi esas alınarak seçildi.\n"
                  + "="*60 + "\n\n")
        outpath.write_text(header + text + "\n", encoding="utf-8")
        manifest.append({"title": title, "author": author, "death_year": death_year,
                         "page_title": chosen["title"], "characters": len(text),
                         "file": str(outpath), "source": "https://tr.wikisource.org/wiki/" + urllib.parse.quote(chosen["title"].replace(" ", "_"))})
        print(f"İNDİ: {title} — {len(text):,} karakter -> {outpath.name}")
        time.sleep(1.2)
    except Exception as e:
        print(f"HATA: {title} — {type(e).__name__}: {e}")
        time.sleep(1.2)

(OUT / "KAYNAKLAR.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
total = sum(x["characters"] for x in manifest)
print(f"\nBİTTİ: {len(manifest)} eser, toplam {total:,} karakter. Kaynak listesi: kitaplar/KAYNAKLAR.json")
