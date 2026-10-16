# -*- coding: utf-8 -*-
"""DataDev AI cluster admin console. Never runs arbitrary commands on workers."""
import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def request_json(base, token, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method="GET" if payload is None else "POST",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            body = {"error": f"HTTP {exc.code}"}
        return exc.code, body
    except Exception as exc:
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def show(title, status, data):
    print("\n" + title)
    print("-" * 54)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if status == 0:
        print("\nKoordinatöre ulaşılamadı. VPN/HTTPS adresini ve bağlantıyı kontrol et.")


def main():
    print("=" * 58)
    print("            DATADEV AI | KÜME YÖNETİM MERKEZİ")
    print("=" * 58)
    base = os.environ.get("DATADEV_CLUSTER_URL", "").strip()
    if not base:
        base = input("VDS koordinatör HTTPS adresi (örn. https://vds.tailnet.ts.net): ").strip()
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        print("Güvenlik: uzak sunucu adresi HTTPS olmalı.")
        return
    token = os.environ.get("DATADEV_CLUSTER_ADMIN_TOKEN", "")
    if len(token) < 32:
        token = getpass.getpass("Yönetici anahtarı (ekrana yazılmaz): ").strip()
    if len(token) < 32:
        print("Yönetici anahtarı en az 32 karakter olmalı.")
        return

    while True:
        print("\n[1] Bağlantı ve görev durumu")
        print("[2] Yeni eğitim turu oluştur (İlter + Mert + VDS)")
        print("[3] Eğitim turunu birleştir ve doğrula")
        print("[4] Koordinatör sağlık kontrolü")
        print("[0] Çıkış")
        choice = input("\nSeçimin: ").strip()
        if choice == "1":
            status, data = request_json(base, token, "/admin/status")
            show("KÜME DURUMU", status, data)
        elif choice == "2":
            raw = input("İşçi başına eğitim adımı (öneri 10-20, varsayılan 20): ").strip()
            try:
                steps = int(raw) if raw else 20
                if not 1 <= steps <= 500:
                    raise ValueError
            except ValueError:
                print("Adım sayısı 1-500 arasında tam sayı olmalı.")
                continue
            status, data = request_json(base, token, "/admin/create-round", {
                "worker_ids": ["ilter-pc", "mert-pc", "vds-worker"],
                "steps": steps,
            })
            show("EĞİTİM TURU OLUŞTURULDU", status, data)
            if status == 201:
                print("\nRound ID (birleştirme için sakla): " + str(data.get("round_id", "")))
                print("İşçilerin çevrimiçi olup görevleri bitirmesini bekle.")
        elif choice == "3":
            round_id = input("Birleştirilecek Round ID: ").strip()
            if not round_id:
                print("Round ID boş olamaz.")
                continue
            confirm = input(f"{round_id} turunu birleştirmek istediğine emin misin? (EVET): ").strip()
            if confirm != "EVET":
                print("İptal edildi.")
                continue
            status, data = request_json(base, token, "/admin/aggregate", {"round_id": round_id})
            show("BİRLEŞTİRME / DOĞRULAMA SONUCU", status, data)
            if status == 200:
                print("\nYeni merkez model sürümü hazır. İşçiler bir sonraki kontrol döngüsünde indirir.")
        elif choice == "4":
            status, data = request_json(base, "", "/health")
            show("KOORDİNATÖR SAĞLIK KONTROLÜ", status, data)
        elif choice == "0":
            print("DataDev AI Küme Yönetim Merkezi kapatıldı.")
            break
        else:
            print("Geçersiz seçim.")


if __name__ == "__main__":
    main()
