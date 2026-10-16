# -*- coding: utf-8 -*-
"""Download only human-approved DataDev Hive records into the local GPT v5 training corpus."""
import json
import shutil
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
IMPORT_FILE = BASE / "datadev_hive_import.jsonl"


def fetch(url, token, node):
    url = url.rstrip("/") + "/api/export?node=" + urllib.parse.quote(node)
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "DataDev-Hive-Sync/1.0",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def key(row):
    q = " ".join(str(row.get("question", "")).split()).casefold()
    a = " ".join(str(row.get("answer", "")).split()).casefold()
    return q + "\n" + a


def main():
    print("\n=== DataDev Hive — Onaylı Veri Aktarımı ===")
    base_url = input("VDS VPN adresi ve portu (ör. http://26.x.x.x:8765): ").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = "http://" + base_url
    token = input("VDS token: ").strip()
    if not token:
        print("Token boş olamaz.")
        return
    node = input("Bu bilgisayarın adı [ilter-pc]: ").strip() or "ilter-pc"
    if base_url.startswith("http://"):
        print("Güvenlik: Bu bağlantıyı yalnızca Radmin VPN gibi güvenilir VPN içinden kullan.")
    try:
        payload = fetch(base_url, token, node)
    except Exception as exc:
        print(f"Aktarım başarısız: {type(exc).__name__}: {exc}")
        return

    remote = payload.get("records", [])
    if not isinstance(remote, list):
        print("VDS geçersiz veri döndürdü; dosya değiştirilmedi.")
        return
    approved = []
    for row in remote:
        if not isinstance(row, dict) or row.get("approved") is not True:
            continue
        q, a = row.get("question"), row.get("answer")
        if isinstance(q, str) and isinstance(a, str) and q.strip() and a.strip():
            approved.append({
                "question": q.strip(),
                "answer": a.strip(),
                "approved": True,
                "source": str(row.get("source", "datadev_hive"))[:80],
            })

    existing = []
    if IMPORT_FILE.exists():
        try:
            for line in IMPORT_FILE.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if isinstance(row, dict) and row.get("approved") is True and row.get("question") and row.get("answer"):
                    existing.append(row)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"Mevcut aktarım dosyası okunamadı ({exc}); hiçbir dosya değiştirilmedi.")
            return

    combined = []
    seen = set()
    for row in existing + approved:
        k = key(row)
        if k not in seen:
            seen.add(k)
            combined.append(row)
    if len(combined) == len(existing):
        print(f"Yeni onaylı kayıt yok. VDS: {len(approved)}; yerel dosya: {len(existing)} kayıt.")
        return

    if IMPORT_FILE.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = IMPORT_FILE.with_name(IMPORT_FILE.name + ".before_sync_" + stamp + ".bak")
        shutil.copy2(IMPORT_FILE, backup)
        print("Önceki aktarım yedeği:", backup.name)

    temp = IMPORT_FILE.with_suffix(".jsonl.tmp")
    temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in combined), encoding="utf-8")
    temp.replace(IMPORT_FILE)
    print(f"Başarılı: {len(approved)} onaylı VDS kaydı alındı; yerel benzersiz toplam {len(combined)}.")
    print("Bu dosya yalnızca insan tarafından onaylanmış kayıtları içerir.")
    print("Sonraki adım: DataDev GPT v5 - Egit.bat ile modeli bu bilgisayarda eğit.")


if __name__ == "__main__":
    main()
