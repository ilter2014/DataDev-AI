# -*- coding: utf-8 -*-
"""DataDev AI overnight teacher-led curriculum builder and safe full-training runner."""
from __future__ import annotations
import ctypes
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
CURRICULUM = BASE / "datadev_curriculum_training.jsonl"
LOG = BASE / "datadev_gece_egitimi.log"
STATE = BASE / "datadev_gece_egitimi_state.json"
MASTER_DATASET = BASE / "datadev_master_dataset.jsonl"
MODEL = BASE / "datadev_gpt_v4_model.pt"
MODEL_BACKUP = BASE / "datadev_gpt_v4_model_before_gece.pt"
MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
HTTP_TIMEOUT = 45
MAX_RETRIES_BEFORE_COOLDOWN = 3
CPU_THREADS = 1

TOPICS = [
    "Python programlama temelleri", "Visual Studio Code ve yazılım araçları",
    "algoritmalar ve problem çözme", "değişkenler ve veri türleri",
    "koşullar ve döngüler", "fonksiyonlar ve modüler kod",
    "hata ayıklama ve test yazma", "veri yapıları ve algoritma karmaşıklığı",
    "HTML CSS ve JavaScript temelleri", "web API ve HTTP",
    "veritabanları ve SQL", "Git ve sürüm kontrolü",
    "işletim sistemleri ve bilgisayar donanımı", "yapay zekâ ve makine öğrenmesi",
    "olasılık ve temel istatistik", "matematiksel akıl yürütme",
    "fizik ve günlük yaşam", "kimya ve temel bilim",
    "Türkçe dil bilgisi ve anlatım", "İngilizce başlangıç seviyesi",
    "Minecraft sunucu yönetimi ve Paper eklentileri", "Skript ve Minecraft otomasyonu",
    "siber güvenlik temelleri ve güvenli parola alışkanlıkları",
    "kaynak değerlendirme ve yanlış bilgiyi fark etme",
    "iletişim, açıklama yapma ve öğretme becerisi"
]

def log(message):
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"stage": 1, "topic_index": 0, "groq_lessons": 0, "local_lessons": 0, "last_topic": ""}

def save_state(state):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)

def append_pairs(pairs, topic, stage, source):
    if not pairs:
        return 0
    existing = set()
    try:
        for line in CURRICULUM.read_text(encoding="utf-8-sig").splitlines():
            try:
                row = json.loads(line)
                existing.add((row.get("language", "tr"), " ".join(str(row.get("question", "")).lower().split())))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    count = 0
    with CURRICULUM.open("a", encoding="utf-8") as f:
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            q = pair.get("question")
            a = pair.get("answer")
            if not isinstance(q, str) or not isinstance(a, str):
                continue
            q, a = q.strip(), a.strip()
            if not (12 <= len(q) <= 500 and 40 <= len(a) <= 2200):
                continue
            key = ("tr", " ".join(q.lower().split()))
            if key in existing:
                continue
            row = {
                "question": q, "answer": a, "language": "tr",
                "source": source, "groq_approved": False,
                "topic": topic, "stage": stage,
                "created_at": datetime.now().astimezone().isoformat()
            }
            serialized = json.dumps(row, ensure_ascii=False)
            f.write(serialized + "\n")
            master_row = dict(row)
            master_row["record_type"] = "training_example"
            with MASTER_DATASET.open("a", encoding="utf-8") as master:
                master.write(json.dumps(master_row, ensure_ascii=False) + "\n")
            existing.add(key)
            count += 1
    return count

def groq_lesson(topic, stage, recent_topics, next_hint=""):
    import datadev_gpt_v4 as core
    key = core.get_groq_api_key()
    if not key:
        raise RuntimeError("Groq API anahtarı bulunamadı; anahtar dosyasının içeriği loglanmayacak.")
    payload = {
        "model": MODEL_NAME,
        "temperature": 0.35,
        "max_tokens": 2800,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content":
                "Sen DataDev AI'nin müfredat öğretmeni ve veri kalite denetçisisin. "
                "DataDev AI'nin yerel küçük modeli için kaliteli Türkçe eğitim örnekleri üret. "
                "Her seferinde tek bir ders aşaması oluştur; konu dışına çıkma, tekrarı azalt. "
                "Sorular gerçek bir kullanıcının sorabileceği doğal sorular olsun. "
                "Yanıtlar kendi başına anlaşılır, doğru, somut, öğretici ve uygun uzunlukta olsun. "
                "Bilmediğin konuda uydurma; gerekiyorsa belirsizliği açıkça belirt. "
                "Tehlikeli veya kötüye kullanım sağlayan yönergeler verme. "
                "Yalnızca JSON döndür: {\"lesson_title\":\"...\",\"next_stage\":\"sonraki mantıklı aşama\","
                "\"pairs\":[{\"question\":\"...\",\"answer\":\"...\"}]}. "
                "pairs dizisinde 6 ile 10 arasında farklı soru-cevap çifti olsun. "
                "Cevapları Türkçe yaz; kod örneği gerekirse kısa ve doğru olsun."
            },
            {"role": "user", "content":
                f"Gece eğitim aşaması: {stage}\nKonu: {topic}\n"
                f"Önceki işlenen konular: {', '.join(recent_topics[-8:]) or 'Henüz yok'}\n"
                f"Önceki öğretmenin sonraki aşama önerisi: {next_hint or 'Belirtilmedi'}\n"
                "Bu aşama için yeni ve kaliteli 6-10 soru-cevap çifti hazırla. "
                "Sadece JSON döndür; açıklama veya Markdown ekleme."}
        ]
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "DataDevAI-NightTutor/1.0"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    try:
        lesson = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError("Groq cevabı geçerli JSON içermiyor.")
        lesson = json.loads(match.group(0))
    pairs = lesson.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 4:
        raise ValueError("Groq dersinde yeterli soru-cevap örneği yok.")
    return lesson

def learn_from_local_records(topic, stage):
    """When Groq is down, create grounded practice pairs from existing local books/articles."""
    import datadev_gpt_v4 as core
    pairs = []
    probes = [
        f"{topic} nedir? Açıkla.",
        f"{topic} konusunda temel kavramlar nelerdir?",
        f"{topic} nasıl çalışır? Basitçe anlat.",
        f"{topic} için yeni başlayanların bilmesi gerekenler nelerdir?"
    ]
    for q in probes:
        try:
            answer = core.retrieve_local_answer(q)
        except Exception:
            answer = None
        if answer and len(answer.strip()) >= 40:
            pairs.append({"question": q, "answer": answer.strip()})
    count = append_pairs(pairs, topic, stage, "local_fallback_from_books_articles")
    log(f"Groq beklerken yerel kaynak tarandı: {topic}; yeni örnek={count}.")
    return count

def set_low_priority_and_keep_awake():
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000) # BELOW_NORMAL
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000002) # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        return True
    except Exception:
        return False

def restore_sleep():
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000) # ES_CONTINUOUS
    except Exception:
        pass

def fine_tune_local(steps=60):
    """Short, low-priority update from saved local/Groq curriculum while the teacher API is unavailable."""
    import torch
    import random
    import datadev_gpt_v4 as core
    if not MODEL.exists():
        log("Ara eğitim atlandı: yerel model dosyası yok.")
        return False
    try:
        torch.set_num_threads(CPU_THREADS)
        saved = torch.load(MODEL, map_location=core.DEVICE, weights_only=False)
        chars = saved["chars"]
        stoi = {ch: i for i, ch in enumerate(chars)}
        train_text, val_text, _, train_count, val_count = core.build_corpus()
        train_ids = torch.tensor([stoi.get(ch, 0) for ch in train_text], dtype=torch.long)
        val_ids = torch.tensor([stoi.get(ch, 0) for ch in val_text], dtype=torch.long)
        if len(train_ids) < core.BLOCK_SIZE + 2 or len(val_ids) < core.BLOCK_SIZE + 2:
            log("Ara eğitim atlandı: eğitim/doğrulama verisi henüz yeterli değil.")
            return False
        val_batches = core.make_batches(val_ids, core.EVAL_BATCHES, random.Random(core.SEED + 1))
        model = core.TinyGPT(len(chars)).to(core.DEVICE)
        model.load_state_dict(saved["model"])
        baseline = core.evaluate(model, val_batches)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.00008, weight_decay=0.02)
        rng = random.Random(core.SEED + int(time.time()) % 100000)
        model.train()
        max_start = len(train_ids) - core.BLOCK_SIZE - 1
        for step in range(max(1, int(steps))):
            starts = [rng.randrange(max_start) for _ in range(core.BATCH_SIZE)]
            xb = torch.stack([train_ids[s:s + core.BLOCK_SIZE] for s in starts])
            yb = torch.stack([train_ids[s + 1:s + core.BLOCK_SIZE + 1] for s in starts])
            _, loss = model(xb, yb)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        updated = core.evaluate(model, val_batches)
        log(f"Ara eğitim tamamlandı: adım={steps}, eğitim örneği={train_count}, doğrulama örneği={val_count}, loss {baseline:.4f} -> {updated:.4f}.")
        # Keep the existing checkpoint unless the same validation batches improve.
        if updated < baseline:
            config = dict(saved.get("config", {}))
            config["night_finetune_steps"] = int(config.get("night_finetune_steps", 0)) + max(1, int(steps))
            config["night_finetune_val_loss"] = updated
            config["night_finetune_at"] = datetime.now().astimezone().isoformat()
            temp_model = MODEL.with_name("datadev_gpt_v4_model.finetune.tmp")
            torch.save({"model": model.state_dict(), "chars": chars, "config": config}, temp_model)
            temp_model.replace(MODEL)
            log("Doğrulama kaybı düştü; iyileşen ara model atomik olarak kaydedildi.")
            return True
        log("Doğrulama kaybı iyileşmedi; mevcut model korunuyor.")
        return False
    except Exception as exc:
        log(f"Ara eğitim hatası: {type(exc).__name__}: {str(exc)[:200]}; mevcut model korunuyor.")
        return False

def run_training():
    import torch
    import datadev_gpt_v4 as core
    torch.set_num_threads(CPU_THREADS)
    log("Toplanan müfredatla tam yerel eğitim başlıyor (CPU tek iş parçacığı, düşük öncelik).")
    if not MODEL.exists():
        log("Mevcut model dosyası bulunamadı; eğitim atlandı.")
        return False
    try:
        shutil.copy2(MODEL, MODEL_BACKUP)
        log(f"Mevcut model yedeklendi: {MODEL_BACKUP.name}")
        core.train()
        if MODEL.exists() and MODEL.stat().st_size > 100_000:
            log("Eğitim işlemi tamamlandı. Yeni model dosyası mevcut; sabah test edilmesi gerekiyor.")
            return True
        raise RuntimeError("Eğitimden sonra model dosyası bulunamadı veya beklenenden küçük.")
    except KeyboardInterrupt:
        log("Eğitim sırasında durduruldu. Yedek model geri yükleniyor.")
        try:
            if MODEL_BACKUP.exists():
                shutil.copy2(MODEL_BACKUP, MODEL)
                log("Önceki model yedekten geri yüklendi.")
        except OSError as restore_exc:
            log(f"Yedekten geri yükleme başarısız: {type(restore_exc).__name__}")
        return False
    except Exception as exc:
        log(f"Eğitim hatası: {type(exc).__name__}: {str(exc)[:250]}. Yedek model geri yükleniyor.")
        try:
            if MODEL_BACKUP.exists():
                shutil.copy2(MODEL_BACKUP, MODEL)
                log("Önceki model yedekten geri yüklendi.")
        except OSError as restore_exc:
            log(f"Yedekten geri yükleme başarısız: {type(restore_exc).__name__}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DataDev AI gece eğitim modu")
    parser.add_argument("--hours", type=float, default=6.0, help="Ders toplama süresi; varsayılan 6 saat, ardından tam eğitim")
    parser.add_argument("--dry-run", action="store_true", help="Ayarları kontrol et, eğitim başlatma")
    args = parser.parse_args()
    if args.hours <= 0 or args.hours > 12:
        parser.error("--hours 0 ile 12 arasında olmalı.")
    if LOG.exists():
        try:
            LOG.rename(LOG.with_name("datadev_gece_egitimi_previous.log"))
        except OSError:
            pass
    if not set_low_priority_and_keep_awake():
        log("Windows güç/öncelik ayarı yapılamadı; normal sistem güç ayarları geçerli olabilir.")
    try:
        import torch
        torch.set_num_threads(CPU_THREADS)
        import datadev_gpt_v4 as core
        log("DATADEV AI GECE EĞİTİM MODU BAŞLADI.")
        log(f"CPU mantıksal çekirdek={os.cpu_count() or 'bilinmiyor'}; Torch iş parçacığı={CPU_THREADS}; öncelik=düşük.")
        log(f"Mevcut yerel kaynaklar: makale={len(list((BASE/'makaleler').glob('*.txt')))}; kitap={len(list((BASE/'kitaplar').glob('*.txt')))}.")
        log(f"Groq modeli={MODEL_NAME}; istek başına zaman aşımı={HTTP_TIMEOUT} sn; paralel istek=1.")
        if args.dry_run:
            log("Deneme modu: Groq isteği ve eğitim çalıştırılmadı.")
            return
        state = read_state()
        deadline = datetime.now().astimezone() + timedelta(hours=args.hours)
        recent_topics = []
        failure_count = 0
        while datetime.now().astimezone() < deadline:
            # Follow teacher progression for four stages, then rotate to a new broad topic to avoid getting stuck.
            broad_switch = int(state.get("groq_lessons", 0)) > 0 and int(state.get("groq_lessons", 0)) % 5 == 0
            topic = (TOPICS[state.get("topic_index", 0) % len(TOPICS)] if broad_switch
                     else str(state.get("next_stage_hint", "")).strip()[:160] or TOPICS[state.get("topic_index", 0) % len(TOPICS)])
            stage = int(state.get("stage", 1))
            state["last_topic"] = topic
            save_state(state)
            try:
                log(f"Groq'dan yeni ders aşaması isteniyor: aşama={stage}, konu={topic}")
                lesson = groq_lesson(topic, stage, recent_topics, "" if broad_switch else state.get("next_stage_hint", ""))
                title = str(lesson.get("lesson_title", topic)).strip()[:160]
                pairs = lesson.get("pairs", [])
                saved = append_pairs(pairs, topic, stage, "groq_teacher_curriculum")
                state["groq_lessons"] = int(state.get("groq_lessons", 0)) + 1
                state["stage"] = stage + 1
                state["topic_index"] = (state.get("topic_index", 0) + 1) % len(TOPICS)
                state["last_lesson_title"] = title
                state["next_stage_hint"] = str(lesson.get("next_stage", "")).strip()[:300]
                state["last_success_at"] = datetime.now().astimezone().isoformat()
                failure_count = 0
                recent_topics.append(topic)
                log(f"DERS KAYDEDİLDİ: {title}; Groq örnekleri={saved}; toplam Groq dersi={state['groq_lessons']}.")
                save_state(state)
                if state["groq_lessons"] % 25 == 0:
                    log("25 Groq dersi tamamlandı; biriken kayıtlardan kontrollü ara eğitim başlıyor.")
                    fine_tune_local(steps=60)
                time.sleep(3)
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError, RuntimeError, OSError) as exc:
                failure_count += 1
                log(f"Groq ders isteği başarısız ({type(exc).__name__}); anahtar/veri gizli tutuldu. Hata sayısı={failure_count}.")
                local_count = learn_from_local_records(topic, stage)
                state["local_lessons"] = int(state.get("local_lessons", 0)) + (1 if local_count else 0)
                save_state(state)
                if failure_count < MAX_RETRIES_BEFORE_COOLDOWN:
                    wait_seconds = min(30 * (2 ** (failure_count - 1)), 120)
                    log(f"{wait_seconds} sn bekleniyor; ardından aynı ders tekrar denenecek.")
                    time.sleep(min(wait_seconds, max(1, (deadline - datetime.now().astimezone()).total_seconds())))
                else:
                    log("Üç başarısız deneme oldu. Önce biriken yerel kayıtlarla ara eğitim yapılacak.")
                    fine_tune_local(steps=80)
                    log("Yerel kaynak işlenerek 5 dakika bekleniyor; sonra aynı Groq dersi yeniden denenecek.")
                    until = min(deadline, datetime.now().astimezone() + timedelta(minutes=5))
                    while datetime.now().astimezone() < until:
                        learn_from_local_records(TOPICS[state.get("topic_index", 0) % len(TOPICS)], stage)
                        time.sleep(60)
                    failure_count = 0
        log("Ders toplama süresi bitti. Kalıcı eğitim kayıtları diskte; tam eğitim başlatılıyor.")
        run_training()
        log("GECE EĞİTİM MODU TAMAMLANDI. Sabah test edin; kalite otomatik olarak garanti edilemez.")
    except KeyboardInterrupt:
        log("Kullanıcı eğitimi durdurdu. Toplanan tüm kayıtlar diskte bırakıldı; tam eğitim başlatılmadı.")
    finally:
        restore_sleep()

if __name__ == "__main__":
    main()
