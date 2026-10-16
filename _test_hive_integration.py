import json
import tempfile
import threading
import urllib.request
from pathlib import Path

import datadev_hive as hive


def call(url, token, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        hive.DATA_DIR = root
        hive.BANK_FILE = root / "bank.jsonl"
        hive.TASK_FILE = root / "tasks.json"
        hive.TOKEN_FILE = root / "server_token.txt"
        hive.STATE_FILE = root / "state.json"
        hive.STATE.clear()
        hive.STATE.update({"nodes": {}, "tasks": {}, "processed": 0, "created": 0})
        token = hive.get_token(True)
        added, duplicates = hive.add_pairs(
            [{"question": "Test sorusu nedir?", "answer": "Bu, onay akışını kontrol etmek için yeterli uzunlukta bir test cevabıdır."}],
            "integration-test"
        )
        assert added == 1 and duplicates == 0

        server = hive.ThreadingHTTPServer(("127.0.0.1", 0), hive.HiveHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_address[1])
        try:
            task = call(base + "/api/task?node=test-worker", token)["task"]
            assert task and task["question"] == "Test sorusu nedir?"
            result = call(base + "/api/result", token, "POST", {
                "id": task["id"], "node": "test-worker",
                "analysis": {"quality_score": 0.8, "recommendation": "candidate"}
            })
            assert result["saved"] is True
            before = call(base + "/api/search?q=Test%20sorusu", token)["results"]
            assert len(before) == 1 and before[0]["approved"] is False
            approved = call(base + "/api/approve", token, "POST", {"id": task["id"]})
            assert approved["approved"] is True
            after = call(base + "/api/search?q=Test%20sorusu", token)["results"]
            assert len(after) == 1 and after[0]["approved"] is True
            print("PASS: token auth, task lease, result submit, approval gate, approved-only search visibility.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
