# -*- coding: utf-8 -*-
"""Admin console for the DataDev AI coordinator. Workers never run arbitrary commands."""
import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def request_json(base, token, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path, data=data,
        method="GET" if payload is None else "POST",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                 "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try: body = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception: body = {"error": f"HTTP {exc.code}"}
        return exc.code, body
    except Exception as exc:
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def show(title, status, data):
    print("\n" + title)
    print("-" * 54)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if status == 0:
        print("\nKoordinatora ulasilamadi. Radmin VPN, URL, firewall ve token'i kontrol et.")


def main():
    print("=" * 58)
    print("            DATADEV AI | KUME YONETIM MERKEZI")
    print("=" * 58)
    base = os.environ.get("DATADEV_CLUSTER_URL", "").strip()
    if not base:
        base = input("VDS Radmin URL'si (or. http://26.x.x.x:8765): ").strip()
    parsed = urllib.parse.urlparse(base)
    host = parsed.hostname or ""
    is_radmin = parsed.scheme == "http" and host.startswith("26.") and parsed.port == 8765
    is_local = parsed.scheme == "http" and host in ("127.0.0.1", "localhost", "::1")
    if not (parsed.scheme == "https" or is_radmin or is_local):
        print("Guvenlik: HTTPS veya yalnizca Radmin VPN uzerindeki http://26.x.x.x:8765 kabul edilir.")
        return
    token = os.environ.get("DATADEV_CLUSTER_ADMIN_TOKEN", "")
    if len(token) < 32:
        token = getpass.getpass("Yonetici anahtari (ekrana yazilmaz): ").strip()
    if len(token) < 32:
        print("Yonetici anahtari en az 32 karakter olmali.")
        return

    while True:
        print("\n[1] Baglanti ve gorev durumu")
        print("[2] Yeni egitim turu olustur (Ilter + Mert + VDS)")
        print("[3] Egitim turunu birlestir ve dogrula")
        print("[4] Koordinator saglik kontrolu")
        print("[0] Cikis")
        choice = input("\nSecimin: ").strip()
        if choice == "1":
            status, data = request_json(base, token, "/admin/status")
            show("KUME DURUMU", status, data)
        elif choice == "2":
            raw = input("Isci basina egitim adimi (onerilen 10-20, varsayilan 20): ").strip()
            try:
                steps = int(raw) if raw else 20
                if not 1 <= steps <= 500: raise ValueError
            except ValueError:
                print("Adim sayisi 1-500 arasinda tam sayi olmali.")
                continue
            status, data = request_json(base, token, "/admin/create-round",
                {"worker_ids": ["ilter-pc", "mert-pc", "vds-worker"], "steps": steps})
            show("EGITIM TURU OLUSTURULDU", status, data)
            if status == 201:
                print("\nRound ID (birlesme icin sakla): " + str(data.get("round_id", "")))
                print("Uc isci cevrimici olup gorevleri bitirince 3. secenegi kullan.")
        elif choice == "3":
            round_id = input("Birlestirilecek Round ID: ").strip()
            if not round_id: print("Round ID bos olamaz."); continue
            if input(f"{round_id} turunu birlestirmek istiyor musun? (EVET): ").strip() != "EVET":
                print("Iptal edildi."); continue
            status, data = request_json(base, token, "/admin/aggregate", {"round_id": round_id})
            show("BIRLESTIRME / DOGRULAMA SONUCU", status, data)
            if status == 200: print("\nYeni model surumu hazir. Isciler sonraki dongude indirir.")
        elif choice == "4":
            status, data = request_json(base, "", "/health")
            show("KOORDINATOR SAGLIK KONTROLU", status, data)
        elif choice == "0":
            print("DataDev AI Kume Yonetim Merkezi kapatildi.")
            break
        else: print("Gecersiz secim.")


if __name__ == "__main__":
    main()
