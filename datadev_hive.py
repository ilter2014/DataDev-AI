#!/usr/bin/env python3
# DataDev Hive - tek dosyalik VDS/Worker bilgi bankasi
# Python 3.10+ | Ek paket gerektirmez
# Not: Worker'lar metinleri analiz eder; bu surum dagitik PyTorch/gradient egitimi yapmaz.
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "DataDev Hive"
VERSION = "0.1.0"
PORT_DEFAULT = 8765
DATA_DIR = Path(__file__).resolve().parent / "hive_data"
BANK_FILE = DATA_DIR / "bank.jsonl"
TASK_FILE = DATA_DIR / "tasks.json"
TOKEN_FILE = DATA_DIR / "server_token.txt"
STATE_FILE = DATA_DIR / "state.json"
LOCK = threading.RLock()
STATE = {"nodes": {}, "tasks": {}, "processed": 0, "created": 0}
LEASES = {}  # record_id -> (worker_name, lease_expiry_epoch)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(value, limit=12000):
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def key_for(question, answer):
    raw = (clean(question).casefold() + "\n" + clean(answer).casefold()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_bank():
    rows = []
    if BANK_FILE.exists():
        with BANK_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except ValueError:
                    continue
    return rows


def write_bank(rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = BANK_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(BANK_FILE)


def get_token(create=False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    if create:
        token = secrets.token_urlsafe(32)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        return token
    return ""


def auth_ok(handler):
    supplied = handler.headers.get("Authorization", "")
    expected = "Bearer " + get_token(False)
    return bool(get_token(False)) and secrets.compare_digest(supplied, expected)


def add_pairs(items, source):
    added, duplicates = 0, 0
    with LOCK:
        rows = load_bank()
        seen = {r.get("key") for r in rows}
        for item in items[:100]:
            q = clean(item.get("question"), 2000)
            a = clean(item.get("answer"), 8000)
            if len(q) < 3 or len(a) < 2:
                continue
            key = key_for(q, a)
            if key in seen:
                duplicates += 1
                continue
            row = {
                "id": uuid.uuid4().hex[:12], "key": key, "question": q,
                "answer": a, "source": clean(source, 80), "created_at": now(),
                "analysis": None, "approved": False
            }
            rows.append(row)
            seen.add(key)
            added += 1
        if added:
            write_bank(rows)
            STATE["created"] = STATE.get("created", 0) + added
            save_json(STATE_FILE, STATE)
    return added, duplicates


def analyze_record(row):
    q, a = clean(row.get("question")), clean(row.get("answer"))
    words = (q + " " + a).split()
    unique = len({w.casefold().strip(".,!?;:()[]{}\"'") for w in words if w.strip()})
    chars = len(q) + len(a)
    score = 0.25
    if len(q) >= 8: score += 0.15
    if len(a) >= 30: score += 0.25
    if len(a) >= 100: score += 0.15
    if unique >= 8: score += 0.10
    if q.casefold() not in a.casefold(): score += 0.10
    score = round(min(score, 1.0), 3)
    return {
        "question_chars": len(q), "answer_chars": len(a), "word_count": len(words),
        "unique_words": unique, "quality_score": score,
        "recommendation": "review" if score < 0.55 else "candidate",
        "processed_at": now()
    }


def bank_stats():
    with LOCK:
        rows = load_bank()
        analysed = sum(1 for r in rows if r.get("analysis"))
        approved = sum(1 for r in rows if r.get("approved"))
        pending = len(rows) - analysed
        nodes = len(STATE.get("nodes", {}))
        return {"records": len(rows), "analysed": analysed, "pending": pending,
                "approved": approved, "nodes_seen": nodes,
                "processed_tasks": STATE.get("processed", 0), "version": VERSION}


def export_training_data():
    # Keep existing manually reviewed examples; add only explicitly approved Hive records.
    target = Path(__file__).resolve().parent / "datadev_interaction_training.jsonl"
    existing = []
    if target.exists():
        for line in target.read_text(encoding="utf-8-sig").splitlines():
            try:
                item = json.loads(line)
                if item.get("question") and item.get("answer"):
                    existing.append({"question": clean(item["question"], 2000),
                                     "answer": clean(item["answer"], 8000)})
            except (ValueError, AttributeError):
                pass
    seen = {key_for(x["question"], x["answer"]) for x in existing}
    rows = existing[:]
    for item in load_bank():
        if item.get("approved"):
            q, a = clean(item.get("question"), 2000), clean(item.get("answer"), 8000)
            key = key_for(q, a)
            if q and a and key not in seen:
                rows.append({"question": q, "answer": a})
                seen.add(key)
    target.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    out = DATA_DIR / "training_dataset.jsonl"
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    return target, len(rows)


def http_json(url, token, method="GET", payload=None, timeout=15):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json",
        "User-Agent": "DataDev-Hive/" + VERSION
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(2_000_000)
        return json.loads(raw.decode("utf-8")) if raw else {}


class HiveHandler(BaseHTTPRequestHandler):
    server_version = "DataDevHive/" + VERSION

    def log_message(self, fmt, *args):
        print("[HTTP] " + (fmt % args))

    def send_json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not auth_ok(self):
            return self.send_json(401, {"error": "Yetkisiz. Token'i kontrol et."})
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        node = clean(query.get("node", ["worker"])[0], 80)
        if parsed.path == "/api/status":
            with LOCK:
                STATE.setdefault("nodes", {})[node] = {"last_seen": now(), "role": "worker"}
                save_json(STATE_FILE, STATE)
            return self.send_json(200, bank_stats())
        if parsed.path == "/api/task":
            with LOCK:
                rows = load_bank()
                epoch = time.time()
                for row in rows:
                    if not row.get("analysis"):
                        lease = LEASES.get(row["id"])
                        if lease and lease[1] > epoch and lease[0] != node:
                            continue
                        LEASES[row["id"]] = (node, epoch + 60)
                        result = {"id": row["id"], "question": row["question"], "answer": row["answer"]}
                        return self.send_json(200, {"task": result})
            return self.send_json(200, {"task": None})
        if parsed.path == "/api/search":
            term = clean(query.get("q", [""])[0], 200).casefold()
            rows = load_bank()
            hits = []
            for row in rows:
                hay = (row.get("question", "") + " " + row.get("answer", "")).casefold()
                if term and term in hay:
                    hits.append({"question": row["question"], "answer": row["answer"],
                                 "approved": row.get("approved", False)})
            return self.send_json(200, {"results": hits[:10]})
        if parsed.path == "/api/export":
            # Only human-approved rows may be exported into the local model's training corpus.
            rows = load_bank()
            records = [{"question": clean(r.get("question"), 2000),
                        "answer": clean(r.get("answer"), 8000),
                        "source": clean(r.get("source", "hive"), 80),
                        "approved": True}
                       for r in rows if r.get("approved") and r.get("question") and r.get("answer")]
            return self.send_json(200, {"records": records, "count": len(records), "exported_at": now()})
        return self.send_json(404, {"error": "Endpoint bulunamadi."})

    def do_POST(self):
        if not auth_ok(self):
            return self.send_json(401, {"error": "Yetkisiz. Token'i kontrol et."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                return self.send_json(413, {"error": "Istek boyutu gecersiz."})
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError):
            return self.send_json(400, {"error": "Gecersiz JSON."})
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/contribute":
            items = body.get("items", [])
            if not isinstance(items, list):
                return self.send_json(400, {"error": "items liste olmali."})
            added, duplicates = add_pairs(items, clean(body.get("node", "worker"), 80))
            return self.send_json(200, {"added": added, "duplicates": duplicates, "stats": bank_stats()})
        if parsed.path == "/api/result":
            record_id = clean(body.get("id"), 40)
            analysis = body.get("analysis")
            if not record_id or not isinstance(analysis, dict):
                return self.send_json(400, {"error": "id/analysis eksik."})
            with LOCK:
                rows = load_bank()
                found = False
                for row in rows:
                    if row.get("id") == record_id:
                        row["analysis"] = analysis
                        found = True
                        break
                LEASES.pop(record_id, None)
                if found:
                    write_bank(rows)
                    STATE["processed"] = STATE.get("processed", 0) + 1
                    node = clean(body.get("node", "worker"), 80)
                    STATE.setdefault("nodes", {})[node] = {"last_seen": now(), "role": "worker"}
                    save_json(STATE_FILE, STATE)
            return self.send_json(200 if found else 404, {"saved": found, "stats": bank_stats()})
        if parsed.path == "/api/approve":
            record_id = clean(body.get("id"), 40)
            with LOCK:
                rows = load_bank()
                found = False
                for row in rows:
                    if row.get("id") == record_id:
                        row["approved"] = True
                        found = True
                        break
                if found:
                    write_bank(rows)
            return self.send_json(200 if found else 404, {"approved": found})
        return self.send_json(404, {"error": "Endpoint bulunamadi."})


def start_vds():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    token = get_token(True)
    STATE.update(read_json(STATE_FILE, STATE))
    port_text = input(f"VDS portu [{PORT_DEFAULT}]: ").strip()
    try:
        port = int(port_text) if port_text else PORT_DEFAULT
        if not 1024 <= port <= 65535: raise ValueError()
    except ValueError:
        print("Gecersiz port."); return
    server = ThreadingHTTPServer(("0.0.0.0", port), HiveHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("\nDataDev Hive VDS hazir.")
    print(f"Port: {port} | Banka: {BANK_FILE}")
    print("WORKER'lara bu token'i guvenli kanaldan ver:")
    print(token)
    print("\nGuvenlik: Bu ilk surum HTTP kullanir. Portu herkese acma; mumkunse VPN/firewall ile yalnizca bilinen cihazlara izin ver.")
    while True:
        print("\n[VDS] 1 Durum  2 Bankaya soru-cevap ekle  3 Bankada ara  4 Onayla  5 Egitim JSONL disa aktar  6 GPT v5 egit  7 Sunucuyu durdur")
        choice = input("> ").strip()
        if choice == "1":
            print(json.dumps(bank_stats(), ensure_ascii=False, indent=2))
        elif choice == "2":
            q = input("Soru: ").strip()
            a = input("Cevap: ").strip()
            print("Sonuc:", add_pairs([{"question": q, "answer": a}], "vds-admin"))
        elif choice == "3":
            term = input("Aranacak kelime: ").strip().casefold()
            for row in load_bank():
                if term and term in (row["question"] + " " + row["answer"]).casefold():
                    print(f"\n[{row['id']}] {row['question']}\n{row['answer']}\nAnaliz={row.get('analysis')} Onay={row.get('approved')}")
        elif choice == "4":
            rid = input("Onaylanacak kayit ID: ").strip()
            with LOCK:
                rows = load_bank()
                found = False
                for row in rows:
                    if row.get("id") == rid:
                        row["approved"] = True; found = True; break
                if found: write_bank(rows)
            print("Onaylandi." if found else "ID bulunamadi.")
        elif choice == "5":
            out, count = export_training_data()
            print(f"{count} toplam egitim ornegi birlestirildi: {out}")
        elif choice == "6":
            out, count = export_training_data()
            trainer = Path(__file__).resolve().parent / "datadev_gpt_v5.py"
            if not trainer.exists():
                print("datadev_gpt_v5.py bulunamadi. GPT v5 dosyalarini bu klasore de koymalisin.")
                continue
            if count < 1:
                print("Egitim verisi bulunamadi."); continue
            steps_text = input("Egitim adimi [300]: ").strip()
            try:
                steps = max(1, min(10000, int(steps_text or "300")))
            except ValueError:
                print("Gecersiz adim sayisi."); continue
            print(f"GPT v5 egitimi basliyor: {count} ornek, {steps} adim. Islem bitene kadar pencereyi kapatma.")
            try:
                result = subprocess.run([sys.executable, str(trainer), "--steps", str(steps)],
                                        cwd=str(trainer.parent), check=False)
                print("Egitim tamamlandi." if result.returncode == 0 else f"Egitim hata kodu: {result.returncode}")
            except OSError as exc:
                print(f"Egitim baslatilamadi: {exc}")
        elif choice == "7":
            server.shutdown()
            print("VDS sunucusu durduruldu."); return
        else:
            print("1-7 arasinda secim yap.")


def worker_loop(base_url, token, node):
    base_url = base_url.rstrip("/")
    print(f"{node} worker calisiyor. Durdurmak icin CTRL+C.")
    while True:
        try:
            status = http_json(base_url + "/api/status?node=" + urllib.parse.quote(node), token)
            response = http_json(base_url + "/api/task?node=" + urllib.parse.quote(node), token)
            task = response.get("task")
            if not task:
                print(f"[{time.strftime('%H:%M:%S')}] Bekliyor | banka={status.get('records', 0)} | bekleyen={status.get('pending', 0)}")
                time.sleep(3)
                continue
            analysis = analyze_record(task)
            result = http_json(base_url + "/api/result", token, "POST", {
                "id": task["id"], "analysis": analysis, "node": node
            })
            print(f"[{task['id']}] analiz tamamlandi | kalite={analysis['quality_score']} | kayit={result.get('saved')}")
        except KeyboardInterrupt:
            print("\nWorker durduruldu."); return
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"Baglanti/istek hatasi: {exc}")
            time.sleep(5)


def worker_menu():
    node = input("Worker adi (or. ilter-pc / mert-pc): ").strip() or "worker-" + str(os.getpid())
    host = input("VDS adresi (or. http://1.2.3.4:8765): ").strip()
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    token = input("VDS token: ").strip()
    if not token:
        print("Token bos olamaz."); return
    while True:
        print("\n[WORKER] 1 Gorevleri calistir  2 Soru-cevap katkisi ekle  3 Yerel JSONL dosyasindan aktar  4 VDS durumunu goster  5 Cikis")
        choice = input("> ").strip()
        try:
            if choice == "1":
                worker_loop(host, token, node)
            elif choice == "2":
                q = input("Soru: ").strip()
                a = input("Cevap: ").strip()
                print(http_json(host.rstrip("/") + "/api/contribute", token, "POST", {
                    "node": node, "items": [{"question": q, "answer": a}]
                }))
            elif choice == "3":
                filename = input("JSONL dosya yolu (her satirda question ve answer): ").strip().strip('"')
                p = Path(filename)
                if not p.is_file():
                    print("Dosya bulunamadi."); continue
                items = []
                with p.open("r", encoding="utf-8-sig") as f:
                    for line in f:
                        try:
                            row = json.loads(line)
                            if row.get("question") and row.get("answer"):
                                items.append({"question": row["question"], "answer": row["answer"]})
                        except (ValueError, AttributeError):
                            continue
                for i in range(0, len(items), 100):
                    print(http_json(host.rstrip("/") + "/api/contribute", token, "POST", {
                        "node": node, "items": items[i:i+100]
                    }))
                print(f"{len(items)} soru-cevap satiri gonderildi.")
            elif choice == "4":
                print(json.dumps(http_json(host.rstrip("/") + "/api/status?node=" + urllib.parse.quote(node), token), ensure_ascii=False, indent=2))
            elif choice == "5":
                return
            else:
                print("1-5 arasinda secim yap.")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"Islem basarisiz: {exc}")


def main():
    print(f"\n=== {APP_NAME} v{VERSION} ===")
    print("Ayni .py dosyasi VDS'de de worker bilgisayarlarinda da kullanilir.")
    print("1) VDS / Banka sunucusu")
    print("2) Worker / Islemci katkilari")
    choice = input("Rol sec: ").strip()
    if choice == "1":
        start_vds()
    elif choice == "2":
        worker_menu()
    else:
        print("1 veya 2 secmelisin.")


if __name__ == "__main__":
    main()
