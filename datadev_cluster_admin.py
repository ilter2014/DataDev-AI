# -*- coding: utf-8 -*-
"""Admin CLI for the DataDev AI coordinator."""
import argparse, json, os, re, urllib.parse, urllib.request, urllib.error


def main():
    parser = argparse.ArgumentParser(description="DataDev AI kume yonetimi")
    parser.add_argument("--server", default=os.environ.get("DATADEV_CLUSTER_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--token", default=os.environ.get("DATADEV_CLUSTER_ADMIN_TOKEN", ""))
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create-round", help="Yeni dagitik egitim turu olustur")
    create.add_argument("--workers", nargs="+", default=["ilter-pc", "mert-pc", "vds-worker"])
    create.add_argument("--steps", type=int, default=20)
    agg = sub.add_parser("aggregate", help="Tamamlanan turun agirliklarini birlestir")
    agg.add_argument("--round-id", required=True)
    sub.add_parser("status", help="Gorev ve model durumunu goster")
    args = parser.parse_args()
    url = args.server.rstrip("/")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    is_radmin = parsed.scheme == "http" and re.fullmatch(r"26\.(\d{1,3}\.){2}\d{1,3}", host) and parsed.port == 8765
    is_local = parsed.scheme == "http" and host in ("127.0.0.1", "localhost", "::1")
    if not (parsed.scheme == "https" or is_radmin or is_local):
        raise SystemExit("Guvenlik: HTTPS veya yalnizca Radmin VPN uzerindeki http://26.x.x.x:8765 kullan.")
    if len(args.token) < 32:
        raise SystemExit("DATADEV_CLUSTER_ADMIN_TOKEN veya --token en az 32 karakter olmali.")
    if args.action == "create-round":
        endpoint, body = "/admin/create-round", {"worker_ids": args.workers, "steps": args.steps}
    elif args.action == "aggregate":
        endpoint, body = "/admin/aggregate", {"round_id": args.round_id}
    else:
        endpoint, body = "/admin/status", None
    request = urllib.request.Request(url + endpoint,
        data=None if body is None else json.dumps(body).encode("utf-8"),
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
