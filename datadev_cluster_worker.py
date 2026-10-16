# -*- coding: utf-8 -*-
"""DataDev AI worker: polls the coordinator, trains one fixed-vocabulary shard, and returns weights."""
from pathlib import Path
import argparse, base64, io, json, os, random, time, urllib.error, urllib.parse, urllib.request

import torch
import datadev_gpt_v5 as core

BASE = Path(__file__).resolve().parent


def request_json(url, token, payload=None, timeout=120):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def train_shard(task, checkpoint_blob, worker_id):
    checkpoint = torch.load(io.BytesIO(checkpoint_blob), map_location="cpu", weights_only=False)
    chars = checkpoint["chars"]
    stoi = {ch: i for i, ch in enumerate(chars)}
    fallback = stoi.get(" ", 0)
    text = task.get("shard_text", "")
    source = torch.tensor([stoi.get(ch, fallback) for ch in text], dtype=torch.long)
    if len(source) < core.BLOCK_SIZE + 2:
        raise ValueError("Bu işçinin eğitim parçası 130 karakterden kısa.")
    model = core.TinyGPT(len(chars)).cpu()
    model.load_state_dict(checkpoint["model"])
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=core.LEARNING_RATE, weight_decay=0.02)
    steps = max(1, min(int(task.get("steps", 20)), 500))
    rng = random.Random(f"{worker_id}:{task.get('task_id')}")
    torch.manual_seed(rng.randrange(1, 2**31 - 1))
    batch_size = core.BATCH_SIZE
    max_start = len(source) - core.BLOCK_SIZE - 1
    started = time.time()
    for step in range(steps):
        starts = [rng.randrange(max_start) for _ in range(batch_size)]
        x = torch.stack([source[pos:pos + core.BLOCK_SIZE] for pos in starts])
        y = torch.stack([source[pos + 1:pos + core.BLOCK_SIZE + 1] for pos in starts])
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 0 or (step + 1) % 10 == 0 or step + 1 == steps:
            print(f"[{worker_id}] adım {step + 1}/{steps} | loss {loss.item():.4f}", flush=True)
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    print(f"[{worker_id}] eğitim parçası bitti: {len(source):,} karakter, {time.time()-started:.1f} sn", flush=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii"), len(source)


def sync_model(base_url, token, worker_id):
    marker = BASE / "datadev_cluster_model_version.txt"
    try:
        local_version = int(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        local_version = -1
    response = request_json(base_url + "/api/model", token, timeout=120)
    remote_version = int(response.get("version", 0))
    if remote_version <= local_version:
        return
    blob = base64.b64decode(response["checkpoint_b64"], validate=True)
    # Verify the checkpoint can be loaded before replacing the local model.
    checkpoint = torch.load(io.BytesIO(blob), map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict) or "model" not in checkpoint or "chars" not in checkpoint:
        raise ValueError("Sunucudan gelen model checkpoint biçimi geçersiz.")
    target = BASE / "datadev_gpt_v5_model.pt"
    temp = target.with_suffix(".pt.sync-tmp")
    temp.write_bytes(blob)
    temp.replace(target)
    marker.write_text(str(remote_version), encoding="utf-8")
    print(f"[{worker_id}] merkez model v{remote_version} indirildi: {target.name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="DataDev AI dağıtık eğitim işçisi")
    parser.add_argument("--server", required=True, help="Örn. https://ai.example.com")
    parser.add_argument("--token", default=os.environ.get("DATADEV_CLUSTER_WORKER_TOKEN", ""))
    parser.add_argument("--worker-id", required=True, help="Örn. ilter-pc, mert-pc veya vds-worker")
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--once", action="store_true", help="Bir görev kontrol edip çık")
    args = parser.parse_args()
    base_url = args.server.rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Güvenlik: uzaktaki sunucu için HTTPS kullan. HTTP yalnızca localhost testinde izinli.")
    if len(args.token) < 32:
        raise SystemExit("DATADEV_CLUSTER_WORKER_TOKEN veya --token en az 32 karakter olmalı.")
    torch.set_num_threads(1)
    print(f"DataDev AI worker hazır: {args.worker_id} -> {base_url}", flush=True)
    while True:
        try:
            sync_model(base_url, args.token, args.worker_id)
            response = request_json(base_url + "/api/claim", args.token, {"worker_id": args.worker_id}, timeout=120)
            task = response.get("task")
            if task:
                print(f"[{args.worker_id}] görev alındı: {task['task_id']} | tur {task['round_id']}", flush=True)
                blob = base64.b64decode(response["checkpoint_b64"], validate=True)
                updated, sample_count = train_shard(task, blob, args.worker_id)
                result = request_json(base_url + "/api/result", args.token, {
                    "task_id": task["task_id"], "worker_id": args.worker_id,
                    "updated_state_b64": updated, "sample_count": sample_count,
                }, timeout=120)
                print(f"[{args.worker_id}] sonuç merkeze gönderildi: {result.get('task_id')}", flush=True)
            elif args.once:
                print(f"[{args.worker_id}] bekleyen görev yok.", flush=True)
                break
            else:
                time.sleep(max(2, min(args.poll_seconds, 60)))
        except KeyboardInterrupt:
            print(f"\n[{args.worker_id}] durduruldu.", flush=True)
            break
        except Exception as exc:
            print(f"[{args.worker_id}] hata: {type(exc).__name__}: {exc}", flush=True)
            if args.once:
                raise SystemExit(1)
            time.sleep(max(5, min(args.poll_seconds * 2, 60)))


if __name__ == "__main__":
    main()
