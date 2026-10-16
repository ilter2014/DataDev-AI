import json
from pathlib import Path
import datadev_gpt_v5 as gpt

path = Path(__file__).resolve().parent / "datadev_hive_import.jsonl"
existed = path.exists()
old = path.read_bytes() if existed else None
approved_q = "Hive approved test question ZQXZ 7421?"
approved_a = "Hive approved test answer ZQXZ 7421."
blocked_q = "Hive unapproved test question ZQXZ 9632?"
blocked_a = "Hive unapproved test answer ZQXZ 9632."
try:
    path.write_text(
        json.dumps({"question": approved_q, "answer": approved_a, "approved": True}, ensure_ascii=False) + "\n" +
        json.dumps({"question": blocked_q, "answer": blocked_a, "approved": False}, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    train_text, _, _, train_count, _ = gpt.build_corpus()
    assert approved_q in train_text and approved_a in train_text, "Approved Hive row was not loaded."
    assert blocked_q not in train_text and blocked_a not in train_text, "Unapproved Hive row leaked into training."
    print(f"PASS: approved Hive rows load; unapproved rows excluded. Training example count={train_count}.")
finally:
    if existed:
        path.write_bytes(old)
    elif path.exists():
        path.unlink()
