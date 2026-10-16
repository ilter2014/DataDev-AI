# -*- coding: utf-8 -*-
"""DataDev AI: local draft -> iterative Groq coaching -> local answer; explicit user-approved learning."""
from pathlib import Path
from datetime import datetime, timezone
import json, time, hashlib

import torch
import datadev_gpt_v4 as core
import datadev_local_knowledge as local_knowledge

BASE = Path(__file__).resolve().parent
MODEL_FILE = BASE / "datadev_gpt_v4_model.pt"
LEGACY_MODEL = BASE / "datadev_gpt_v3_model.pt"
LOOP_LOG = BASE / "datadev_review_loop.jsonl"
CANDIDATES = BASE / "datadev_loop_candidates.jsonl"
USER_LEARNING = BASE / "datadev_user_learning.jsonl"
MAX_ROUNDS = 8
MAX_NEW_TOKENS = 160

def now():
    return datetime.now(timezone.utc).isoformat()

def append_jsonl(path, item):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

def load_local_model():
    active = MODEL_FILE if MODEL_FILE.exists() else LEGACY_MODEL
    if not active.exists():
        raise FileNotFoundError("Model dosyası bulunamadı. Önce DataDev GPT v4 eğitimini tamamla.")
    checkpoint = torch.load(active, map_location=core.DEVICE, weights_only=False)
    chars = checkpoint["chars"]
    model = core.TinyGPT(len(chars)).to(core.DEVICE)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model, chars, {ch: i for i, ch in enumerate(chars)}, active

def local_draft(question, model, chars, stoi, feedback=None, previous_draft=""):
    qnorm = " ".join(core.normalize_words(question))
    safe_fallback = "Bu soruya şu an güvenilir bir yerel cevabım yok; yanlış bilgi uydurmak istemem. Konuyu biraz daraltır veya bir kaynak/metin paylaşırsan tekrar deneyebilirim."
    if feedback is not None:
        return safe_fallback
    if feedback is None:
        reliable = local_knowledge.answer(question)
        if reliable:
            return reliable
    if feedback is None and qnorm in {"merhaba", "selam", "sa", "hey"}:
        return "Merhaba! Ben DataDev AI. Sana nasıl yardımcı olabilirim?"
    if feedback is None and (qnorm in {"adin", "ismin"} or "kimsin" in qnorm):
        return "Ben DataDev AI; yerel bilgisayarda eğitilen küçük bir dil modeli prototipiyim."
    if feedback is None:
        grounded = core.retrieve_local_answer(question)
        if grounded:
            return grounded
    return safe_fallback

def save_user_learning(question, answer, source, groq_reason=""):
    record = {
        "timestamp": now(),
        "question": question.strip(),
        "answer": answer.strip(),
        "language": "tr",
        "source": source,
        "groq_reason": groq_reason,
        "human_approved": True,
        "groq_approved": source == "user_approved_groq_answer",
        "review_status": "approved_for_training",
        "training_eligible": True
    }
    # Avoid exact duplicate pairs in the user-approved learning file.
    digest = hashlib.sha256((record["question"].casefold() + "\n" + record["answer"].casefold()).encode("utf-8")).hexdigest()
    if USER_LEARNING.exists():
        for line in USER_LEARNING.read_text(encoding="utf-8-sig").splitlines():
            try:
                item = json.loads(line)
                old = hashlib.sha256((str(item.get("question", "")).casefold() + "\n" + str(item.get("answer", "")).casefold()).encode("utf-8")).hexdigest()
                if old == digest:
                    return False
            except json.JSONDecodeError:
                continue
    append_jsonl(USER_LEARNING, record)
    append_jsonl(LOOP_LOG, {"timestamp": now(), "event": "user_learning_approved", "question": question, "answer": answer, "source": source})
    return True

def run_chat():
    torch.set_num_threads(1)
    model, chars, stoi, model_path = load_local_model()
    if not core.get_groq_api_key():
        print("HATA: Groq API anahtarı bulunamadı. Groq onayı olmadan cevap gönderilmeyecek.")
        return 2

    print("=" * 66)
    print("DATADEV AI — YEREL MODEL + GROQ GERİ BİLDİRİM DÖNGÜSÜ")
    print("DataDev AI her turda kendi cevabını üretir; Groq yalnızca öğretmenlik yapar.")
    print("Groq onayından sonra cevap gönderilir. En fazla 8 tur; takılırsa onaysız durur.")
    print("Cevaptan sonra /onayla veya /duzelt <senin doğru cevabın> ile senden öğrenmesini sağla.")
    print("Sorular ve turlar:", LOOP_LOG.name, "| onaylı öğrenme:", USER_LEARNING.name)
    print("Çıkış: /cikis | Model:", model_path.name)
    print("=" * 66)

    last_exchange = None
    while True:
        try:
            question = input("\nSen > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÇıkılıyor; kayıtlar saklandı.")
            return 0
        if not question:
            continue
        low = question.lower()
        if low in {"/cikis", "/exit", "exit"}:
            return 0
        if low == "/onayla":
            if not last_exchange:
                print("Onaylanacak son cevap yok.")
            elif not last_exchange.get("approved", False):
                print("Bu taslağı Groq onaylamadı. Otomatik onaylayamazsın; doğru cevabı /duzelt <cevap> ile kaydedebilirsin.")
            else:
                saved = save_user_learning(last_exchange["question"], last_exchange["answer"], "user_approved_groq_answer", last_exchange.get("groq_reason", ""))
                print("Bu soru-cevap eğitim için " + ("kaydedildi." if saved else "zaten kayıtlıydı.") + " Modelin ağırlıkları sonraki eğitimde güncellenir.")
            continue
        if low.startswith("/duzelt "):
            corrected = question[len("/duzelt "):].strip()
            if not last_exchange:
                print("Düzeltilecek son cevap yok.")
            elif not corrected:
                print("Kullanım: /duzelt Burada senin doğru cevabın")
            else:
                saved = save_user_learning(last_exchange["question"], corrected, "user_corrected_answer", last_exchange.get("groq_reason", "Kullanıcı cevabı düzeltti."))
                append_jsonl(LOOP_LOG, {"timestamp": now(), "event": "user_correction", "question": last_exchange["question"], "previous_answer": last_exchange["answer"], "user_corrected_answer": corrected})
                print("Düzeltmen " + ("onaylı eğitim örneği olarak kaydedildi." if saved else "zaten kayıtlıydı.") + " Sonraki model eğitiminde kullanılacak.")
            continue
        if low == "/soncevap":
            print(last_exchange["answer"] if last_exchange else "Henüz onaylanmış cevap yok.")
            continue

        started = time.time()
        draft = local_draft(question, model, chars, stoi)
        print("\n[Tur 1] DataDev AI taslağı > " + draft)
        seen = set()
        approved = False
        groq_reason = ""
        feedback = ""
        round_no = 0
        while round_no < MAX_ROUNDS:
            round_no += 1
            fingerprint = " ".join(draft.casefold().split())
            if fingerprint in seen:
                append_jsonl(LOOP_LOG, {"timestamp": now(), "question": question, "round": round_no, "event": "repeated_draft_stop", "draft": draft, "feedback": feedback, "model": model_path.name})
                print("DURDU: DataDev AI aynı taslağı tekrarladı. Groq onayı olmadığı için cevap gönderilmiyor.")
                break
            seen.add(fingerprint)
            review = core.groq_review(question, draft, language="tr")
            groq_reason = review.get("reason", "")
            event = {
                "timestamp": now(), "question": question, "round": round_no, "draft": draft,
                "groq_status": review.get("status"), "groq_decision": review.get("decision"),
                "groq_feedback": groq_reason, "groq_suggested_correction": review.get("final_answer", ""),
                "model": model_path.name
            }
            append_jsonl(LOOP_LOG, event)
            print(f"\n[GROQ — Tur {round_no}] Durum: {review.get('status')} | Karar: {review.get('decision')}")
            print("Yorum:", groq_reason)
            if review.get("status") != "ok":
                print("Groq denetimi başarısız. Güvenli davranmak için cevap gönderilmiyor.")
                break
            if review.get("decision") == "KEEP":
                approved = True
                print("\n[GROQ ONAYLADI] Sana gönderilen cevap yerel DataDev AI taslağıdır:")
                print("DataDev AI > " + draft)
                append_jsonl(CANDIDATES, {
                    "timestamp": now(), "question": question, "answer": draft,
                    "human_approved": False, "groq_approved": True, "review_status": "needs_human_review",
                    "training_eligible": False, "rounds": round_no,
                    "note": "Groq onaylı yerel cevap adayı; kullanıcı /onayla demeden eğitime eklenmez."
                })
                append_jsonl(LOOP_LOG, {"timestamp": now(), "question": question, "round": round_no, "event": "approved_and_sent", "answer_sent": draft, "elapsed_seconds": round(time.time()-started, 2), "model": model_path.name})
                last_exchange = {"question": question, "answer": draft, "groq_reason": groq_reason, "rounds": round_no, "approved": True}
                break
            feedback = groq_reason + "\nÖnerilen düzeltme / yalnızca öğretim ipucu: " + review.get("final_answer", "")
            previous_draft = draft
            draft = local_draft(question, model, chars, stoi, feedback=feedback, previous_draft=previous_draft)
            print(f"\n[Tur {round_no + 1}] DataDev AI yeni taslağı > {draft}")
        if not approved:
            print("\nBu soru için onaylı cevap gönderilmedi. Taslaklar ve denetim kayıtları saklandı.")
            last_exchange = {"question": question, "answer": draft, "groq_reason": groq_reason, "rounds": round_no, "approved": False}

if __name__ == "__main__":
    try:
        raise SystemExit(run_chat())
    except KeyboardInterrupt:
        print("\nDöngü kullanıcı tarafından durduruldu; kayıtlar saklandı.")
        raise SystemExit(130)
