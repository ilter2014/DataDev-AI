# -*- coding: utf-8 -*-
"""AKTA deposundan seçili kamu malı klasiklerin Türkçe bölümlerini indirir."""
from pathlib import Path
import json, time, urllib.request

BASE = Path(__file__).resolve().parent
OUT = BASE / "kitaplar"
OUT.mkdir(exist_ok=True)
HEADERS = {"User-Agent": "DataDevAI/1.0 (local educational model; public-domain corpus)"}
RAW = "https://raw.githubusercontent.com/ahmetax/akta/main/"
IDS = ["PG10002", "PG19551", "PG221"]

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read()

req = urllib.request.Request(
    "https://raw.githubusercontent.com/ahmetax/akta/main/metadata.jsonl",
    headers=HEADERS
)
metadata_text = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
metadata = [json.loads(line) for line in metadata_text.splitlines() if line.strip()]
by_id = {str(item.get("gutenberg_id", "")): item for item in metadata}
manifest = []

for gid in IDS:
    item = by_id.get(gid)
    if not item:
        print(f"PAS: {gid} metadata içinde yok.")
        continue
    rel = str(item.get("file_path", "")).replace("\\", "/")
    rel = rel.removeprefix("../")
    if not rel or ".." in rel.split("/"):
        print(f"PAS: Güvenli olmayan dosya yolu: {rel}")
        continue
    try:
        raw = get(RAW + rel).decode("utf-8", errors="replace")
        start = raw.find("*** START OF TURKISH PART ***")
        end = raw.find("*** END OF TURKISH PART ***")
        if start < 0 or end <= start:
            print(f"PAS: {gid} içinde Türkçe bölüm işaretleri yok.")
            continue
        body = raw[start + len("*** START OF TURKISH PART ***"):end].strip()
        if len(body) < 15000:
            print(f"PAS: {gid} Türkçe bölüm kısa ({len(body):,} karakter).")
            continue
        title = item.get("turkish_title") or item.get("original_title") or gid
        author = item.get("author") or "Bilinmiyor"
        safe = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title).strip().replace(" ", "_")
        filename = f"AKTA_{gid}_{safe[:65]}.txt"
        source = item.get("gutenberg_link", "")
        header = f"{title}\nYazar: {author}\nKaynak: {source}\nTürkçe metin arşivi: AKTA / Project Gutenberg\n" + "=" * 60 + "\n\n"
        target = OUT / filename
        target.write_text(header + body + "\n", encoding="utf-8")
        manifest.append({"title": title, "author": author, "gutenberg_id": gid,
                         "source": source, "file": filename, "characters": len(body),
                         "archive": "https://github.com/ahmetax/akta"})
        print(f"İNDİRİLDİ: {title} — {len(body):,} Türkçe karakter -> {filename}")
        time.sleep(2)
    except Exception as e:
        print(f"HATA: {gid} — {type(e).__name__}: {e}")
        time.sleep(2)

(OUT / "AKTA_KAYNAKLAR.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nBİTTİ: {len(manifest)} kitap/metin, toplam {sum(x['characters'] for x in manifest):,} Türkçe karakter.")
