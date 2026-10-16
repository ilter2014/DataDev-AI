# -*- coding: utf-8 -*-
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
BASE=Path(__file__).resolve().parent
MASTER=BASE/"datadev_master_dataset.jsonl"
SOURCES=[
 ("datadev_curriculum_training.jsonl","training_example"),
 ("datadev_interaction_training.jsonl","approved_interaction"),
 ("datadev_benchmark_questions.jsonl","benchmark_question"),
 ("datadev_benchmark_results.jsonl","benchmark_result"),
 ("datadev_api_requests.jsonl","interaction_event"),
]
seen_sigs=set()
seen_semantic=set()
if MASTER.exists():
    for line in MASTER.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        try:
            row=json.loads(line)
            sig=row.get("_source_signature")
            if sig: seen_sigs.add(sig)
            kind=row.get("record_type","")
            semantic=(kind,row.get("question"),row.get("answer"),row.get("run_id"),row.get("test_id"),row.get("timestamp"))
            seen_semantic.add(semantic)
        except Exception: pass
added=0
with MASTER.open("a",encoding="utf-8") as out:
    for filename,kind in SOURCES:
        path=BASE/filename
        if not path.exists(): continue
        for lineno,line in enumerate(path.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
            if not line.strip(): continue
            sig=hashlib.sha256((filename+"\0"+line).encode("utf-8")).hexdigest()
            if sig in seen_sigs: continue
            try: row=json.loads(line)
            except Exception: row={"raw_record":line}
            if not isinstance(row,dict): row={"value":row}
            row=dict(row)
            row.setdefault("record_type",kind)
            semantic=(row.get("record_type",kind),row.get("question"),row.get("answer"),row.get("run_id"),row.get("test_id"),row.get("timestamp"))
            if semantic in seen_semantic: continue
            row["_source_file"]=filename
            row["_source_line"]=lineno
            row["_source_signature"]=sig
            row["_imported_at"]=datetime.now(timezone.utc).isoformat()
            out.write(json.dumps(row,ensure_ascii=False)+"\n")
            seen_sigs.add(sig); seen_semantic.add(semantic); added+=1
print("Master dataset:",MASTER.name)
print("Records now:",len(seen_semantic),"; newly imported:",added)
