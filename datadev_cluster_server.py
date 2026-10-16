# -*- coding: utf-8 -*-
"""DataDev AI private coordinator: queues local training shards and averages model updates."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
import argparse, base64, io, json, os, random, secrets, threading, uuid

import torch
import datadev_gpt_v5 as core

BASE = Path(__file__).resolve().parent
ROOT = BASE / "datadev_cluster"
TASKS = ROOT / "tasks"
RESULTS = ROOT / "results"
MODEL_FILE = BASE / "datadev_gpt_v5_model.pt"
LOCK = threading.Lock()
ADMIN_TOKEN = ""
WORKER_TOKEN = ""


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def load_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if fallback is None else fallback


def model_checkpoint():
    if not MODEL_FILE.exists():
        raise FileNotFoundError("Önce datadev_gpt_v5.py ile v5 modelini eğit; model dosyası bulunamadı.")
    return torch.load(MODEL_FILE, map_location="cpu", weights_only=False)


def checkpoint_bytes(checkpoint):
    buffer = io.BytesIO()
    torch.save(checkpoint, buffer)
    return buffer.getvalue()


def authorized(handler, expected):
    header = handler.headers.get("Authorization", "")
    supplied = header[7:].strip() if header.lower().startswith("bearer ") else ""
    return bool(expected) and secrets.compare_digest(supplied, expected)


def send_json(handler, status, payload):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    server_version = "DataDevCluster/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 15 * 1024 * 1024:
            raise ValueError("İstek gövdesi sınırı aşıldı (15 MiB).")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self):
        if self.path == "/health":
            return send_json(self, 200, {"ok": True, "service": "DataDev AI coordinator", "time": now()})
        if self.path == "/api/model":
            if not authorized(self, WORKER_TOKEN):
                return send_json(self, 401, {"error": "Yetkisiz worker"})
            try:
                checkpoint = model_checkpoint()
                meta = load_json(ROOT / "meta.json", {"version": 0})
                return send_json(self, 200, {
                    "version": int(meta.get("version", 0)),
                    "checkpoint_b64": base64.b64encode(checkpoint_bytes(checkpoint)).decode("ascii"),
                })
            except Exception as exc:
                return send_json(self, 503, {"error": str(exc)})
        if self.path == "/admin/status":
            if not authorized(self, ADMIN_TOKEN):
                return send_json(self, 401, {"error": "Yetkisiz yönetici"})
            tasks = [load_json(p) for p in TASKS.glob("*.json")]
            counts = {}
            for task in tasks:
                key = task.get("status", "unknown")
                counts[key] = counts.get(key, 0) + 1
            meta = load_json(ROOT / "meta.json", {"version": 0})
            return send_json(self, 200, {"model_version": meta.get("version", 0), "tasks": counts, "task_count": len(tasks)})
        return send_json(self, 404, {"error": "Bulunamadı"})

    def do_POST(self):
        is_worker_path = self.path in ("/api/claim", "/api/result")
        expected = WORKER_TOKEN if is_worker_path else ADMIN_TOKEN
        if not authorized(self, expected):
            return send_json(self, 401, {"error": "Yetkisiz istek"})
        try:
            body = self.read_body()
            if self.path == "/api/claim":
                worker_id = str(body.get("worker_id", "")).strip()
                if not worker_id or len(worker_id) > 80:
                    return send_json(self, 400, {"error": "worker_id gerekli (en fazla 80 karakter)."})
                with LOCK:
                    for path in sorted(TASKS.glob("*.json")):
                        task = load_json(path)
                        if task.get("status") != "pending":
                            continue
                        preferred = task.get("preferred_worker")
                        if preferred and preferred != worker_id:
                            continue
                        task["status"] = "claimed"
                        task["worker_id"] = worker_id
                        task["claimed_at"] = now()
                        save_json(path, task)
                        checkpoint = model_checkpoint()
                        model_b64 = base64.b64encode(checkpoint_bytes(checkpoint)).decode("ascii")
                        return send_json(self, 200, {
                            "task": task,
                            "checkpoint_b64": model_b64,
                            "model_version": load_json(ROOT / "meta.json", {"version": 0}).get("version", 0),
                        })
                return send_json(self, 200, {"task": None})
            if self.path == "/api/result":
                task_id = str(body.get("task_id", "")).strip()
                worker_id = str(body.get("worker_id", "")).strip()
                update_b64 = body.get("updated_state_b64")
                sample_count = int(body.get("sample_count", 0))
                if not task_id or not worker_id or not isinstance(update_b64, str) or sample_count < 1:
                    return send_json(self, 400, {"error": "Sonuç alanları eksik."})
                path = TASKS / (task_id + ".json")
                with LOCK:
                    task = load_json(path, None)
                    if not task or task.get("status") != "claimed" or task.get("worker_id") != worker_id:
                        return send_json(self, 409, {"error": "Görev bulunamadı, tamamlanmış veya bu işçiye ait değil."})
                    update = base64.b64decode(update_b64, validate=True)
                    if len(update) > 10 * 1024 * 1024:
                        return send_json(self, 413, {"error": "Model güncellemesi 10 MiB sınırını aşıyor."})
                    result_path = RESULTS / (task_id + ".pt")
                    result_path.parent.mkdir(parents=True, exist_ok=True)
                    result_path.write_bytes(update)
                    task.update({"status": "done", "sample_count": sample_count, "result_file": result_path.name, "finished_at": now()})
                    save_json(path, task)
                print(f"Sonuç alındı: {task_id} / {worker_id} ({sample_count:,} karakter)", flush=True)
                return send_json(self, 200, {"ok": True, "task_id": task_id})
            if self.path == "/admin/create-round":
                worker_ids = body.get("worker_ids", ["ilter-pc", "mert-pc", "vds-worker"])
                steps = max(1, min(int(body.get("steps", 20)), 500))
                if not isinstance(worker_ids, list) or not worker_ids or len(worker_ids) > 16:
                    return send_json(self, 400, {"error": "worker_ids 1-16 elemanlı liste olmalı."})
                checkpoint = model_checkpoint()
                train_text, _, _, _, _ = core.build_corpus()
                if len(train_text) < core.BLOCK_SIZE + 2:
                    return send_json(self, 400, {"error": "Eğitim metni çok kısa."})
                round_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
                shard_size = (len(train_text) + len(worker_ids) - 1) // len(worker_ids)
                created = []
                with LOCK:
                    for index, worker_id in enumerate(worker_ids):
                        worker_id = str(worker_id).strip()
                        if not worker_id or len(worker_id) > 80:
                            continue
                        shard = train_text[index * shard_size:(index + 1) * shard_size]
                        if len(shard) < core.BLOCK_SIZE + 2:
                            continue
                        task_id = round_id + "-" + worker_id.replace(" ", "_") + "-" + uuid.uuid4().hex[:4]
                        task = {
                            "task_id": task_id, "round_id": round_id, "task_type": "train_shard",
                            "preferred_worker": worker_id, "status": "pending", "steps": steps,
                            "shard_text": shard, "sample_count": len(shard), "created_at": now(),
                        }
                        save_json(TASKS / (task_id + ".json"), task)
                        created.append({"task_id": task_id, "worker_id": worker_id, "characters": len(shard)})
                meta = load_json(ROOT / "meta.json", {"version": 0})
                meta.update({"last_round_id": round_id, "expected_workers": len(created), "updated_at": now()})
                save_json(ROOT / "meta.json", meta)
                print(f"Yeni eğitim turu: {round_id} — {len(created)} işçi, {steps} adım/işçi", flush=True)
                return send_json(self, 201, {"round_id": round_id, "steps_per_worker": steps, "tasks": created})
            if self.path == "/admin/aggregate":
                round_id = str(body.get("round_id", "")).strip()
                if not round_id:
                    return send_json(self, 400, {"error": "round_id gerekli."})
                with LOCK:
                    round_tasks = [load_json(p) for p in TASKS.glob("*.json") if load_json(p).get("round_id") == round_id]
                    if not round_tasks:
                        return send_json(self, 404, {"error": "Eğitim turu bulunamadı."})
                    unfinished = [t for t in round_tasks if t.get("status") != "done"]
                    if unfinished:
                        return send_json(self, 409, {"error": "Bütün işçiler bitirmedi.", "pending_or_running": len(unfinished)})
                    updates = []
                    for task in round_tasks:
                        result_path = RESULTS / task["result_file"]
                        state = torch.load(result_path, map_location="cpu", weights_only=True)
                        updates.append((state, max(1, int(task.get("sample_count", 1)))))
                    checkpoint = model_checkpoint()
                    base_state = checkpoint["model"]
                    expected_keys = set(base_state.keys())
                    for state, _ in updates:
                        if set(state.keys()) != expected_keys or any(state[k].shape != base_state[k].shape for k in expected_keys):
                            return send_json(self, 400, {"error": "Model güncellemesi mimariyle uyuşmuyor; mevcut model korunuyor."})
                    keys = updates[0][0].keys()
                    total = sum(weight for _, weight in updates)
                    averaged = {}
                    for key in keys:
                        first = updates[0][0][key]
                        if torch.is_floating_point(first):
                            acc = torch.zeros_like(first)
                            for state, weight in updates:
                                acc += state[key] * (weight / total)
                            averaged[key] = acc
                        else:
                            averaged[key] = first
                    # Evaluate the candidate on the fixed validation split before replacing the active model.
                    _, val_text, _, _, _ = core.build_corpus()
                    chars = checkpoint["chars"]
                    stoi = {ch: i for i, ch in enumerate(chars)}
                    fallback = stoi.get(" ", 0)
                    val_ids = torch.tensor([stoi.get(ch, fallback) for ch in val_text], dtype=torch.long)
                    val_batches = core.make_batches(val_ids, core.EVAL_BATCHES, random.Random(2027))
                    baseline_model = core.TinyGPT(len(chars)).cpu()
                    baseline_model.load_state_dict(checkpoint["model"])
                    baseline_loss = core.evaluate(baseline_model, val_batches)
                    candidate_model = core.TinyGPT(len(chars)).cpu()
                    candidate_model.load_state_dict(averaged)
                    candidate_loss = core.evaluate(candidate_model, val_batches)
                    if candidate_loss > baseline_loss + 0.05:
                        return send_json(self, 409, {"error": "Doğrulama kaybı kötüleşti; aktif model korunuyor.", "baseline_val_loss": round(baseline_loss, 4), "candidate_val_loss": round(candidate_loss, 4)})
                    meta = load_json(ROOT / "meta.json", {"version": 0})
                    backup_dir = ROOT / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    version = int(meta.get("version", 0))
                    backup_path = backup_dir / f"datadev_gpt_v5_model_v{version}.pt"
                    if not backup_path.exists():
                        backup_path.write_bytes(MODEL_FILE.read_bytes())
                    checkpoint["model"] = averaged
                    checkpoint.setdefault("config", {})["distributed_round"] = round_id
                    checkpoint["config"]["federated_workers"] = len(updates)
                    checkpoint["config"]["federated_steps_per_worker"] = round_tasks[0].get("steps", 0)
                    temp = MODEL_FILE.with_suffix(".pt.tmp")
                    torch.save(checkpoint, temp)
                    temp.replace(MODEL_FILE)
                    meta = load_json(ROOT / "meta.json", {"version": 0})
                    meta["version"] = int(meta.get("version", 0)) + 1
                    meta["last_aggregated_round"] = round_id
                    meta["updated_at"] = now()
                    save_json(ROOT / "meta.json", meta)
                return send_json(self, 200, {"ok": True, "round_id": round_id, "model_version": meta["version"], "workers_aggregated": len(updates), "baseline_val_loss": round(baseline_loss, 4), "candidate_val_loss": round(candidate_loss, 4), "model_file": MODEL_FILE.name})
            return send_json(self, 404, {"error": "Bulunamadı"})
        except FileNotFoundError as exc:
            return send_json(self, 503, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            return send_json(self, 400, {"error": str(exc)})
        except Exception as exc:
            print(f"İstek hatası: {type(exc).__name__}: {exc}", flush=True)
            return send_json(self, 500, {"error": f"{type(exc).__name__}: {exc}"})


def main():
    global ADMIN_TOKEN, WORKER_TOKEN
    parser = argparse.ArgumentParser(description="DataDev AI güvenli görev dağıtıcı ve FedAvg koordinatörü")
    parser.add_argument("--host", default=os.environ.get("DATADEV_CLUSTER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DATADEV_CLUSTER_PORT", "8765")))
    parser.add_argument("--admin-token", default=os.environ.get("DATADEV_CLUSTER_ADMIN_TOKEN", ""))
    parser.add_argument("--worker-token", default=os.environ.get("DATADEV_CLUSTER_WORKER_TOKEN", ""))
    args = parser.parse_args()
    ADMIN_TOKEN, WORKER_TOKEN = args.admin_token, args.worker_token
    if len(ADMIN_TOKEN) < 32 or len(WORKER_TOKEN) < 32:
        raise SystemExit("Güvenlik için DATADEV_CLUSTER_ADMIN_TOKEN ve DATADEV_CLUSTER_WORKER_TOKEN en az 32 karakter olmalı.")
    for folder in (TASKS, RESULTS):
        folder.mkdir(parents=True, exist_ok=True)
    meta_path = ROOT / "meta.json"
    if not meta_path.exists():
        save_json(meta_path, {"version": 0, "created_at": now()})
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DataDev AI koordinatörü {args.host}:{args.port} üzerinde hazır.", flush=True)
    print("Uç noktalar: /health, /api/claim, /api/result, /api/model, /admin/create-round, /admin/aggregate, /admin/status", flush=True)
    print("İnternete doğrudan açma: özel VPN (ör. Tailscale) veya HTTPS reverse proxy kullan.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Koordinatör kapatılıyor...", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
