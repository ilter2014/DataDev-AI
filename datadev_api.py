# -*- coding: utf-8 -*-
"""DataDev AI local API prototype. Defaults to localhost; not production-ready."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import threading
import time
import sys
from datetime import datetime, timezone

# Groq may return Unicode punctuation (for example U+202F) unsupported by Windows console code pages.
# Keep console diagnostics from crashing otherwise successful chat requests.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import torch
import datadev_gpt_v5 as core

BASE = Path(__file__).resolve().parent
MAX_BODY_BYTES = 16_384
MAX_QUESTION_CHARS = 2_000
RATE_LIMIT_COUNT = 20
RATE_LIMIT_WINDOW = 60
MODEL_LOCK = threading.Lock()
_MODEL = None
_CHARS = None
_STOI = None
_MODEL_MTIME = None
_RATE_LOCK = threading.Lock()
_REQUESTS = defaultdict(deque)


def is_loopback_host(host: str) -> bool:
    return host.lower() in {"127.0.0.1", "localhost", "::1"}


def load_local_model():
    """Load or reload the local checkpoint when its file timestamp changes."""
    global _MODEL, _CHARS, _STOI, _MODEL_MTIME
    with MODEL_LOCK:
        candidates = [
            BASE / "datadev_gpt_v5_model.pt",
            BASE / "datadev_gpt_v5_model.pt",
        ]
        checkpoint = next((p for p in candidates if p.exists()), None)
        if checkpoint is None:
            raise FileNotFoundError("Model dosyasi bulunamadi. Once model egitimini tamamlayin.")
        checkpoint_mtime = checkpoint.stat().st_mtime
        if _MODEL is not None and _MODEL_MTIME == checkpoint_mtime:
            return _MODEL, _CHARS, _STOI
        saved = torch.load(checkpoint, map_location=core.DEVICE, weights_only=False)
        chars = saved.get("chars")
        state = saved.get("model")
        if not isinstance(chars, list) or not state:
            raise RuntimeError("Model checkpoint formati beklenenden farkli.")
        model = core.TinyGPT(len(chars)).to(core.DEVICE)
        model.load_state_dict(state)
        model.eval()
        _MODEL, _CHARS, _STOI = model, chars, {ch: i for i, ch in enumerate(chars)}
        _MODEL_MTIME = checkpoint_mtime
        print("[DataDev API] Local model loaded/reloaded from " + checkpoint.name, flush=True)
        return _MODEL, _CHARS, _STOI

def find_learned_answer(question: str, language: str = "tr"):
    """Use Groq-approved local answers as persistent, immediately available examples."""
    path = BASE / "datadev_interaction_training.jsonl"
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    qwords = set(core.normalize_words(question))
    if not qwords:
        return None
    best = (0.0, None)
    qnorm = " ".join(core.normalize_words(question))
    for row in rows:
        if row.get("language", "tr") != language:
            continue
        q = row.get("question", "")
        a = row.get("answer", "")
        if not isinstance(q, str) or not isinstance(a, str) or not a.strip():
            continue
        if "groq_approved" not in str(row.get("source", "")) and not row.get("groq_approved"):
            continue
        if " ".join(core.normalize_words(q)) == qnorm:
            return a.strip()
        words = set(core.normalize_words(q))
        if not words:
            continue
        overlap = len(qwords & words)
        score = overlap / max(len(qwords), len(words))
        if overlap >= 2 and score > best[0]:
            best = (score, a.strip())
    return best[1] if best[0] >= 0.72 else None


def save_groq_approved_example(question: str, answer: str, language: str, reason: str) -> bool:
    """Persist only locally generated answers that Groq explicitly approved."""
    if not question.strip() or not answer.strip():
        return False
    path = BASE / "datadev_interaction_training.jsonl"
    rows = []
    if path.exists():
        try:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        except (OSError, UnicodeError, json.JSONDecodeError):
            rows = []
    qnorm = " ".join(core.normalize_words(question))
    for row in rows:
        if row.get("language", "tr") == language and " ".join(core.normalize_words(str(row.get("question", "")))) == qnorm:
            # Refresh an existing approved example with the newest accepted answer.
            row.update({"answer": answer.strip(), "groq_reason": reason, "groq_approved": True,
                        "source": "groq_approved_local_answer", "updated_at": datetime.now(timezone.utc).isoformat()})
            path.write_text("".join(json.dumps(item, ensure_ascii=False) + chr(10) for item in rows), encoding="utf-8")
            master_row = dict(row)
            master_row["record_type"] = "approved_interaction"
            with (BASE / "datadev_master_dataset.jsonl").open("a", encoding="utf-8") as master:
                master.write(json.dumps(master_row, ensure_ascii=False) + chr(10))
            return True
    rows.append({"question": question.strip(), "answer": answer.strip(), "language": language,
                 "groq_reason": reason, "groq_approved": True, "source": "groq_approved_local_answer",
                 "approved_at": datetime.now(timezone.utc).isoformat()})
    try:
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + chr(10) for item in rows), encoding="utf-8")
        master_row = dict(rows[-1])
        master_row["record_type"] = "approved_interaction"
        with (BASE / "datadev_master_dataset.jsonl").open("a", encoding="utf-8") as master:
            master.write(json.dumps(master_row, ensure_ascii=False) + chr(10))
        return True
    except OSError:
        return False


def make_local_draft(question: str, language: str = "tr", coaching: str = "") -> str:
    # Every candidate is generated by the local model. Groq feedback is coaching only.
    language = "en" if str(language).lower().startswith("en") else "tr"
    if not coaching:
        learned = find_learned_answer(question, language)
        if learned:
            return learned
    if not coaching and language == "tr":
        qnorm = " ".join(core.normalize_words(question))
        if qnorm in {"merhaba", "selam", "sa", "hey"}:
            return "Selam! Ben DataDev AI. Nasıl yardımcı olayım?"
        if qnorm in {"adin", "ismin"} or "kimsin" in qnorm:
            return "Ben DataDev AI. Sorularını yerel modelim ve bilgi kaynaklarımla yanıtlamaya çalışan bir yapay zekâ prototipiyim."
        if any(x in qnorm for x in ["nasilsin", "naber", "ne haber"]):
            return "İyiyim dostum, teşekkür ederim! Sen nasılsın? Sana nasıl yardımcı olabilirim?"
    if not coaching:
        grounded = core.retrieve_local_answer(question)
        if grounded and language == "tr":
            return grounded
    model, chars, stoi = load_local_model()
    if language == "en":
        prompt = "User: " + question + "\n"
        if coaching:
            prompt += "Teacher feedback for DataDev AI: " + coaching + "\nRewrite your own answer using this feedback, do not copy blindly.\n"
        prompt += "DataDev AI (answer in English):"
    else:
        prompt = "Kullanıcı: " + question + "\n"
        if coaching:
            prompt += "Öğretmen geri bildirimi: " + coaching + "\nBu geri bildirimi dikkate alıp kendi cevabını yeniden oluştur.\n"
        prompt += "DataDev AI (Türkçe cevap ver):"
    ids = [stoi.get(ch, 0) for ch in prompt][-core.BLOCK_SIZE:]
    inp = torch.tensor([ids], dtype=torch.long)
    with MODEL_LOCK:
        with torch.inference_mode():
            out = model.generate(inp, max_new_tokens=100, temperature=0.45 if coaching else 0.55, top_k=8)[0].tolist()
    decoded = "".join(chars[i] for i in out)
    answer = decoded.split("DataDev AI", 1)[-1].split("\nKullanıcı:", 1)[0].strip(" :\n")
    return answer or ("My local model could not produce a reliable answer yet." if language == "en" else "Yerel model bu soruya henüz tutarlı bir cevap üretemedi.")


def is_allowed_question(value) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= MAX_QUESTION_CHARS


def log_chat_event(event: dict) -> None:
    """Append chat diagnostics locally; never include API keys or auth headers."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    log_path = BASE / "datadev_api_requests.jsonl"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print("[DataDev API] Log yazılamadı: " + type(exc).__name__, flush=True)
    print("\n========== DATADEV AI İSTEK KAYDI ==========" , flush=True)
    print("Soru: " + str(event.get("question", "")), flush=True)
    print("Yerel taslak: " + str(event.get("draft", "")), flush=True)
    print("Groq durumu: " + str(event.get("groq_status", "unknown")), flush=True)
    print("Groq kararı: " + str(event.get("groq_decision", "unknown")), flush=True)
    print("Son cevap: " + str(event.get("answer", "")), flush=True)
    print("=============================================\n", flush=True)


def rate_limited(client: str) -> bool:
    now = time.monotonic()
    with _RATE_LOCK:
        q = _REQUESTS[client]
        while q and now - q[0] > RATE_LIMIT_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT_COUNT:
            return True
        q.append(now)
        return False


class DataDevHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(api_token: str, require_auth: bool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DataDevAI-API/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Avoid logging request bodies, questions, or credentials.
            print("[DataDev API] " + (fmt % args))

        def send_json(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            if not require_auth:
                return True
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + api_token
            return secrets.compare_digest(supplied, expected)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                self.send_json(200, {
                    "ok": True,
                    "service": "datadev-ai-api",
                    "version": "0.1",
                    "model_checkpoint_present": any(
                        (BASE / name).exists()
                        for name in ("datadev_gpt_v5_model.pt",)
                    ),
                    "groq_configured": bool(core.get_groq_api_key()),
                    "mode": "local-first"
                })
                return
            self.send_json(404, {"error": "not_found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/v1/chat":
                self.send_json(404, {"error": "not_found"})
                return
            if not self.authorized():
                self.send_json(401, {"error": "unauthorized"})
                return
            client = self.client_address[0]
            if rate_limited(client):
                self.send_json(429, {"error": "rate_limited", "retry_after_seconds": RATE_LIMIT_WINDOW})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            if size <= 0 or size > MAX_BODY_BYTES:
                self.send_json(413, {"error": "invalid_body_size", "max_bytes": MAX_BODY_BYTES})
                return
            try:
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(400, {"error": "invalid_json"})
                return
            question = payload.get("question") if isinstance(payload, dict) else None
            if not is_allowed_question(question):
                self.send_json(400, {
                    "error": "invalid_question",
                    "max_characters": MAX_QUESTION_CHARS
                })
                return
            question = question.strip()
            language = "en" if str(payload.get("language", "tr")).lower().startswith("en") else "tr"
            try:
                # Iterative coaching loop: local model writes every candidate; Groq critiques it.
                # At most 3 review rounds per user message; stop early if Groq approves.
                # Groq's suggested answer is never sent directly to the user.
                draft = make_local_draft(question, language)
                rounds = []
                result = {}
                answer = draft
                learned_saved = False
                for round_number in range(1, 4):
                    result = core.groq_review(question, answer, language=language)
                    round_record = {
                        "round": round_number,
                        "datadev_said": answer,
                        "groq_decision": result.get("decision", "unknown"),
                        "groq_said": result.get("reason", ""),
                        "groq_suggestion": result.get("final_answer", "")
                    }
                    rounds.append(round_record)
                    print(f"\n--- TUR {round_number} ---", flush=True)
                    print("DATADEV AI DEDİ: " + str(answer), flush=True)
                    print("GROQ DEDİ: " + str(result.get("reason", "")), flush=True)
                    print("GROQ ÖNERİSİ (doğrudan kullanıcıya gönderilmez): " + str(result.get("final_answer", "")), flush=True)
                    if result.get("status") != "ok":
                        break
                    if result.get("decision") == "KEEP":
                        learned_saved = save_groq_approved_example(question, answer, language, str(result.get("reason", "")))
                        if learned_saved:
                            print("[DataDev AI] Groq onaylı örnek kalıcı öğrenme dosyasına kaydedildi.", flush=True)
                        break
                    if round_number == 3:
                        break
                    coaching = "Groq değerlendirmesi: " + str(result.get("reason", "")) + "\nÖneri: " + str(result.get("final_answer", ""))
                    revised = make_local_draft(question, language, coaching=coaching)
                    # Even if the local draft repeats itself, ask Groq to review again up to the hard cap.
                    if revised and revised.strip():
                        answer = revised
                mode = "yerel_model_groq_geri_bildirim_dongusu" if result.get("status") == "ok" else "yalnizca_yerel_model"
                log_chat_event({
                    "question": question,
                    "language": language,
                    "draft": draft,
                    "answer": answer,
                    "groq_suggestion": result.get("final_answer", ""),
                    "rounds": rounds,
                    "round_count": len(rounds),
                    "mode": mode,
                    "groq_status": result.get("status", "unknown"),
                    "groq_decision": result.get("decision", "unknown"),
                    "groq_reason": result.get("reason", ""),
                    "learned_saved": learned_saved
                })
                self.send_json(200, {
                    "answer": answer,
                    "mode": mode,
                    "language": language,
                    "groq_reviewed": result.get("status") == "ok",
                    "rounds": rounds,
                    "round_count": len(rounds),
                    "learned_saved": learned_saved,
                    "notice": "DataDev AI cevabı üretir. Groq en fazla 3 tur öğretmen geri bildirimi verir; Groq onaylarsa yerel cevap ve soru kalıcı öğrenme örneği olarak kaydedilir."
                })
            except FileNotFoundError as exc:
                self.send_json(503, {"error": "model_unavailable", "detail": str(exc)})
            except Exception as exc:
                # Keep detailed diagnostics locally; never expose stack traces or credentials to callers.
                import traceback
                detail = traceback.format_exc()
                try:
                    with (BASE / "datadev_api_errors.log").open("a", encoding="utf-8") as error_log:
                        error_log.write("\\n===== " + datetime.now(timezone.utc).isoformat() + " =====\\n")
                        error_log.write("Question: " + str(question)[:200] + "\\n")
                        error_log.write(detail + "\\n")
                except OSError:
                    pass
                print("[DataDev API] Request failed: " + type(exc).__name__ + ": " + str(exc)[:300], flush=True)
                self.send_json(500, {"error": "internal_error", "detail": type(exc).__name__})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="DataDev AI API prototype")
    parser.add_argument("--host", default="127.0.0.1", help="Default is local-only (127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port 1-65535 aralığında olmalı.")
    external = not is_loopback_host(args.host)
    token = os.environ.get("DATADEV_API_TOKEN", "").strip()
    if external and len(token) < 32:
        parser.error("Dış ağda dinlemek için en az 32 karakterlik DATADEV_API_TOKEN ortam değişkeni zorunlu.")
    server = DataDevHTTPServer((args.host, args.port), make_handler(token, external or bool(token)))
    print(f"DataDev AI API dinliyor: http://{args.host}:{args.port}")
    print("Sağlık kontrolü: GET /health")
    print("Sohbet: POST /v1/chat  JSON: {\"question\":\"Merhaba\"}")
    if external:
        print("UYARI: Bu prototip üretim yayını değildir; HTTPS/reverse proxy, hesap kimliği ve kalıcı kota henüz yok.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nDataDev API durduruluyor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
