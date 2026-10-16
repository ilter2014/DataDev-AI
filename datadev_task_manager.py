# -*- coding: utf-8 -*-
"""DataDev AI local coordinator: tasks, worker packets, and safe candidate imports."""
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE / "datadev_tasks"
PENDING = ROOT / "pending"
DONE = ROOT / "done"
INBOX = BASE / "datadev_worker_results" / "inbox"
PROCESSED = BASE / "datadev_worker_results" / "processed"
PACKETS = BASE / "datadev_worker_packets"
CANDIDATES = BASE / "datadev_worker_candidates.jsonl"
WORKERS = ["colab-1", "colab-2", "kayizer-vds", "birsunucum-vds", "github-actions"]


def now():
    return datetime.now(timezone.utc).isoformat()


def ensure():
    for folder in [PENDING, DONE, INBOX, PROCESSED, PACKETS]:
        folder.mkdir(parents=True, exist_ok=True)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export():
    tasks = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PENDING.glob("*.json"))]
    save(PACKETS / "all_tasks.json", {"project": "DataDev AI", "generated_at": now(), "tasks": tasks})
    for worker in WORKERS:
        save(PACKETS / f"{worker}_tasks.json", {
            "worker_id": worker,
            "tasks": [task for task in tasks if task.get("preferred_worker") == worker],
        })
    print("Görev paketleri yenilendi:", PACKETS)


def seed():
    jobs = [
        ("qa_generation", "Python temelleri", "colab-1", 30, "Türkçe Python soru-cevap çiftleri üret; tekrar etme."),
        ("qa_generation", "Minecraft Paper ve Skript", "colab-2", 25, "Paper 1.21.x ve Skript hakkında Türkçe soru-cevap üret; emin olmadığını uydurma."),
        ("qa_generation", "SQL ve veritabanları", "kayizer-vds", 25, "SQL ve veritabanları hakkında Türkçe soru-cevap üret."),
        ("dataset_audit", "Veri kalite denetimi", "birsunucum-vds", 0, "Veriyi değiştirmeden tekrarları ve şüpheli kayıtları raporla."),
        ("qa_generation", "Türkçe anlatım", "github-actions", 20, "Türkçe anlatım ve belirsizlik hakkında soru-cevap üret."),
    ]
    for kind, topic, worker, count, instructions in jobs:
        task_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        save(PENDING / f"{task_id}.json", {
            "task_id": task_id, "task_type": kind, "topic": topic,
            "preferred_worker": worker, "expected_records": count,
            "instructions": instructions, "status": "pending", "created_at": now(),
        })
    export()
    print("5 görev oluşturuldu. Aynı görev grubunu tekrar oluşturmak istemiyorsan 1'i yeniden seçme.")


def load_known_task(task_id):
    pending_path = PENDING / f"{task_id}.json"
    done_path = DONE / f"{task_id}.json"
    if pending_path.exists():
        return pending_path, json.loads(pending_path.read_text(encoding="utf-8"))
    if done_path.exists():
        return done_path, json.loads(done_path.read_text(encoding="utf-8"))
    return None, None


def import_results():
    files = sorted(INBOX.glob("*.json"))
    if not files:
        print("Gelen kutusunda sonuç JSON dosyası yok:", INBOX)
        return
    known_ids = set()
    if CANDIDATES.exists():
        with CANDIDATES.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    if item.get("record_id"):
                        known_ids.add(item["record_id"])
                except json.JSONDecodeError:
                    continue

    imported = 0
    for result_path in files:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ATLANDI: {result_path.name} okunamadı: {exc}")
            continue

        task_id = result.get("task_id")
        worker_id = result.get("worker_id")
        records = result.get("records")
        if not isinstance(task_id, str) or not task_id or not isinstance(records, list):
            print(f"ATLANDI: {result_path.name} şema/task_id hatalı.")
            continue
        task_path, task = load_known_task(task_id)
        if task is None:
            print(f"ATLANDI: Bilinmeyen görev: {task_id}. Görev dosyası bulunamadı.")
            continue
        if task.get("preferred_worker") != worker_id:
            print(f"ATLANDI: {task_id} için beklenen işçi {task.get('preferred_worker')}, gelen {worker_id}.")
            continue
        if task.get("status") == "result_received_needs_review":
            print(f"ATLANDI: {task_id} daha önce içe aktarılmış görünüyor.")
            continue

        valid_records = []
        invalid_count = 0
        for record in records:
            if not isinstance(record, dict):
                invalid_count += 1
                continue
            question = record.get("question")
            answer = record.get("answer")
            record_id = record.get("record_id")
            if (not isinstance(question, str) or not question.strip() or len(question) > 2000
                    or not isinstance(answer, str) or not answer.strip() or len(answer) > 8000
                    or not isinstance(record_id, str) or not record_id.strip()):
                invalid_count += 1
                continue
            if record_id in known_ids:
                continue
            candidate = dict(record)
            candidate.update({
                "record_type": "worker_candidate",
                "task_id": task_id,
                "worker_id": worker_id,
                "language": candidate.get("language", "tr"),
                "human_approved": False,
                "groq_approved": False,
                "review_status": "needs_review",
                "training_eligible": False,
                "received_at": now(),
                "worker_result_file": result_path.name,
            })
            valid_records.append(candidate)
            known_ids.add(record_id)

        if not valid_records:
            print(f"ATLANDI: {task_id} içinde aktarılabilir yeni kayıt yok (geçersiz: {invalid_count}).")
            continue

        with CANDIDATES.open("a", encoding="utf-8", newline="\n") as handle:
            for candidate in valid_records:
                handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")

        task["status"] = "result_received_needs_review"
        task["received_records"] = len(valid_records)
        task["invalid_records"] = invalid_count
        task["result_received_at"] = now()
        task["result_file"] = result_path.name
        task["review_status"] = "needs_review"
        destination_task = DONE / task_path.name
        save(destination_task, task)
        if task_path.parent == PENDING:
            task_path.unlink()
        destination_result = PROCESSED / f"{task_id}__{result_path.name}"
        if destination_result.exists():
            destination_result = PROCESSED / f"{task_id}__{datetime.now().strftime('%H%M%S')}__{result_path.name}"
        shutil.move(str(result_path), str(destination_result))
        imported += len(valid_records)
        print(f"İçe aktarıldı: {task_id} — {len(valid_records)} aday; geçersiz atlanan: {invalid_count}.")
        print("Sonuç:", destination_result)

    print(f"Toplam yeni aday: {imported}")
    print("Aday havuzu:", CANDIDATES)
    print("GÜVENLİK: Ana eğitim veri kümesi değiştirilmedi; adaylar otomatik eğitime uygun değil.")


def show_status():
    pending = list(PENDING.glob("*.json"))
    done = list(DONE.glob("*.json"))
    inbox = list(INBOX.glob("*.json"))
    processed = list(PROCESSED.glob("*.json"))
    candidate_count = 0
    if CANDIDATES.exists():
        with CANDIDATES.open("r", encoding="utf-8") as handle:
            candidate_count = sum(1 for line in handle if line.strip())
    print("Bekleyen görev:", len(pending))
    print("Sonucu alınmış/tamamlanan görev:", len(done))
    print("Gelen sonuç dosyası:", len(inbox))
    print("İşlenmiş sonuç dosyası:", len(processed))
    print("İnsan incelemesi bekleyen aday:", candidate_count)


def main():
    ensure()
    while True:
        print("\nDATADEV AI GÖREV MERKEZİ")
        print("1 Görev grubu oluştur")
        print("2 Görev paketlerini yenile")
        print("3 Durum")
        print("4 Gelen sonuçları güvenli biçimde içe aktar")
        print("5 Çıkış")
        choice = input("Seçim: ").strip()
        if choice == "1":
            seed()
        elif choice == "2":
            export()
        elif choice == "3":
            show_status()
        elif choice == "4":
            import_results()
        elif choice == "5":
            break
        else:
            print("Geçersiz seçim.")


if __name__ == "__main__":
    main()
