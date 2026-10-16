import json, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path
base = Path(__file__).resolve().parent
api = base / "datadev_api.py"
subprocess.run([sys.executable, "-m", "py_compile", str(api)], check=True)
print("SYNTAX: OK")
sys.path.insert(0, str(base))
import datadev_api
assert datadev_api.is_loopback_host("127.0.0.1")
assert datadev_api.is_loopback_host("localhost")
assert not datadev_api.is_loopback_host("0.0.0.0")
assert not datadev_api.is_loopback_host("192.0.2.1")
print("HOST POLICY HELPERS: PASS")
proc = subprocess.Popen([sys.executable, str(api), "--host", "127.0.0.1", "--port", "18765"], cwd=str(base), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    health = None
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18765/health", timeout=1) as r:
                health = json.loads(r.read().decode("utf-8"))
            break
        except Exception:
            time.sleep(0.25)
    assert health and health["ok"] and health["model_checkpoint_present"]
    print("HEALTH: PASS", health)
    body = json.dumps({"question":"Python nedir?"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:18765/v1/chat", data=body, headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read().decode("utf-8"))
    assert result.get("answer") and result.get("mode") in {"local_fallback","groq_reviewed"}
    print("CHAT: PASS; mode =", result["mode"], "; answer chars =", len(result["answer"]))
    bad = urllib.request.Request("http://127.0.0.1:18765/v1/chat", data=b'{"question":""}', headers={"Content-Type":"application/json"}, method="POST")
    try:
        urllib.request.urlopen(bad, timeout=3)
        raise AssertionError("Empty question should fail")
    except urllib.error.HTTPError as e:
        assert e.code == 400, e.code
        print("VALIDATION: PASS (empty question rejected)")
    print("SMOKE TEST: PASS")
finally:
    proc.terminate()
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired: proc.kill()
