# -*- coding: utf-8 -*-
"""Admin CLI for the DataDev AI coordinator."""
import argparse, json, os, urllib.parse, urllib.request, urllib.error


def main():
    parser = argparse.ArgumentParser(description="DataDev AI küme yönetimi")
    parser.add_argument("--server", default=os.environ.get("DATADEV_CLUSTER_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token", default=os.environ.get("DATADEV_CLUSTER_ADMIN_TOKEN", ""))
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create-round", help="Yeni dağıtık eğitim turu oluştur")
    create.add_argument("--workers", nargs="+", default=["ilter-pc", "mert-pc", "vds-worker"])
    create.add_argument("--steps", type=int, default=20)
    agg = sub.add_parser("aggregate", help="Tamamlanan turun ağırlıklarını birleştir")
    agg.add_argument("--round-id", required=True)
    sub.add_parser("status", help="Görev ve model durumunu göster")
    args = parser.parse_args()
    url = args.server.rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Güvenlik: uzaktaki koordinatör için HTTPS kullan.")
    if len(args.token) < 32:
        raise SystemExit("DATADEV_CLUSTER_ADMIN_TOKEN veya --token en az 32 karakter olmalı.")
    if args.action == "create-round":
        endpoint, body = "/admin/create-round", {"worker_ids": args.workers, "steps": args.steps}
    elif args.action == "aggregate":
        endpoint, body = "/admin/aggregate", {"round_id": args.round_id}
    else:
        endpoint, body = "/admin/status", None
    request = urllib.request.Request(url + endpoint, data=None if body is None else json.dumps(body).encode("utf-8"),
        method="GET" if body is None else "POST",
        headers={"Authorization": "Bearer " + args.token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            print(json.dumps(json.loads(response.read().decode("utf-8")), ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
