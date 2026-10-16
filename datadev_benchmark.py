# -*- coding: utf-8 -*-
"""DataDev AI repeatable local benchmark. No training, no Groq calls."""
from __future__ import annotations
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
TESTS = BASE / "datadev_benchmark_questions.jsonl"
RESULTS = BASE / "datadev_benchmark_results.jsonl"
REPORT = BASE / "datadev_benchmark_report.txt"
MODEL = BASE / "datadev_gpt_v4_model.pt"

def now():
    return datetime.now().astimezone().isoformat()

def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    if path == RESULTS:
        master_obj = dict(obj)
        master_obj["record_type"] = "benchmark_result"
        with (BASE / "datadev_master_dataset.jsonl").open("a", encoding="utf-8") as master:
            master.write(json.dumps(master_obj, ensure_ascii=False) + "\n")

def main():
    import subprocess
    sync_script = BASE / "datadev_dataset_backfill.py"
    if sync_script.exists():
        subprocess.run([sys.executable, str(sync_script)], cwd=str(BASE), check=False)
    import torch
    import datadev_gpt_v4 as core
    torch.set_num_threads(1)
    if not MODEL.exists():
        print("HATA: datadev_gpt_v4_model.pt bulunamadi. Model testi yapilamadi.")
        print("Not: Bu test egitim baslatmaz.")
        return 2
    checkpoint = torch.load(MODEL, map_location=core.DEVICE, weights_only=False)
    chars = checkpoint.get("chars")
    weights = checkpoint.get("model")
    if not isinstance(chars, list) or not weights:
        print("HATA: Model dosyasi beklenen bicimde degil.")
        return 3
    model = core.TinyGPT(len(chars)).to(core.DEVICE)
    model.load_state_dict(weights)
    model.eval()
    stoi = {ch:i for i,ch in enumerate(chars)}
    mtime = datetime.fromtimestamp(MODEL.stat().st_mtime).astimezone().isoformat()
    questions = [json.loads(line) for line in TESTS.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    session = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    records = []
    print("DATADEV AI BENCHMARK — yalnizca test; model egitilmez.")
    print("Model:", MODEL.name, "| Son degisiklik:", mtime, "| Test:", len(questions))
    for index, item in enumerate(questions, 1):
        q = item["question"]
        started = time.time()
        source = "local_model"
        try:
            # Match the local app's retrieval-first behavior; no Groq API call.
            grounded = core.retrieve_local_answer(q)
            if grounded:
                answer = grounded
                source = "local_retrieval"
            else:
                prompt = "Kullanıcı: " + q + "\nDataDev AI:"
                ids = [stoi.get(ch, 0) for ch in prompt][-core.BLOCK_SIZE:]
                inp = torch.tensor([ids], dtype=torch.long)
                with torch.inference_mode():
                    out = model.generate(inp, max_new_tokens=180, temperature=0.55, top_k=8)[0].tolist()
                decoded = "".join(chars[i] for i in out)
                answer = decoded.split("DataDev AI:", 1)[-1].split("\nKullanıcı:", 1)[0].strip()
                if not answer:
                    answer = "(Model bos cevap uretti.)"
        except Exception as exc:
            answer = "[TEST HATASI] " + type(exc).__name__ + ": " + str(exc)[:240]
            source = "test_error"
        elapsed = round(time.time() - started, 3)
        normalized = " ".join(answer.lower().split())
        words = re.findall(r"\w+", normalized, flags=re.UNICODE)
        repetition = 1.0 - (len(set(words)) / max(1, len(words)))
        auto_flags = []
        if len(answer.strip()) < 12: auto_flags.append("cevap_cok_kisa")
        if len(words) >= 25 and repetition > 0.55: auto_flags.append("yuksek_tekrar_suphesi")
        if "test hatasi" in answer.lower(): auto_flags.append("calisma_hatasi")
        record = {
            "run_id": run_id, "timestamp": now(), "test_id": item["id"],
            "category": item["category"], "question": q, "answer": answer,
            "answer_source": source, "checkpoint": MODEL.name,
            "checkpoint_mtime": mtime, "latency_seconds": elapsed,
            "auto_flags": auto_flags, "expected_concepts": item.get("expected_concepts", []),
            "must_not": item.get("must_not", []),
            "human_rating_0_to_5": None, "human_correct": None,
            "human_notes": "", "review_status": "needs_human_review"
        }
        append_jsonl(RESULTS, record)
        records.append(record)
        print(f"\n[{index}/{len(questions)}] {item['id']} — {item['category']} ({source}, {elapsed}s)")
        print("SORU:", q)
        print("CEVAP:", answer[:1200])
        if auto_flags: print("UYARI:", ", ".join(auto_flags))
    with REPORT.open("w", encoding="utf-8") as f:
        f.write("DATADEV AI BENCHMARK RAPORU\n")
        f.write("Calisma: " + session + "\nRun ID: " + run_id + "\n")
        f.write("Checkpoint: " + MODEL.name + "\nCheckpoint degisikligi: " + mtime + "\n")
        f.write("Toplam soru: " + str(len(records)) + "\n")
        f.write("Bu rapor otomatik bir zeka puani vermez; dogruluk ve kalite insan incelemesi ister.\n\n")
        for r in records:
            f.write("="*72 + "\n")
            f.write(f"{r['test_id']} | {r['category']} | kaynak={r['answer_source']} | {r['latency_seconds']}s\n")
            f.write("SORU: " + r["question"] + "\nCEVAP:\n" + r["answer"] + "\n")
            f.write("Kontrol edilecek kavramlar: " + ", ".join(r["expected_concepts"]) + "\n")
            f.write("Otomatik uyarilar: " + (", ".join(r["auto_flags"]) or "yok") + "\n")
            f.write("Insan puani (0-5): [sonradan doldur]\nDogru mu?: [evet/hayir]\nNot: \n\n")
    print("\nTamamlandi. Model degistirilmedi; egitim yapilmadi.")
    print("Sonuclar:", RESULTS.name)
    print("Okunabilir rapor:", REPORT.name)
    print("Dikkat: Beklenen kavramlar otomatik dogruluk puani degildir; cevaplari gozden gecir.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
