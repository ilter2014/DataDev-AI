# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path(__file__).resolve().parent
log_path = base / "datadev_api_requests.jsonl"

print("DataDev AI - İstek / Prompt kayıtları")
print("=" * 60)
if not log_path.exists():
    print("Henüz kayıt yok. Önce DataDev AI API üzerinden bir soru gönder.")
    input("\nÇıkmak için Enter...")
    raise SystemExit(0)

count = 0
with log_path.open("r", encoding="utf-8") as f:
    for line in f:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        count += 1
        print(f"\n[{count}] {item.get('timestamp', 'zaman yok')}")
        print("Soru: " + str(item.get("question", "")))
        print("Yerel taslak: " + str(item.get("draft", "")))
        print("Groq durumu: " + str(item.get("groq_status", "unknown")))
        print("Groq kararı: " + str(item.get("groq_decision", "unknown")))
        print("Groq gerekçesi: " + str(item.get("groq_reason", "")))
        print("Son cevap: " + str(item.get("answer", "")))
        print("Mod: " + str(item.get("mode", "unknown")))
        print("-" * 60)

print(f"\nToplam kayıt: {count}")
print("Not: Bu kayıtlar eğitim değildir; istek ve cevap geçmişidir.")
input("\nÇıkmak için Enter...")
