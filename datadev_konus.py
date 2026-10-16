# -*- coding: utf-8 -*-
"""DataDev AI: conversational assistant with optional OpenAI-compatible API and local fallback."""
from pathlib import Path
import json
import os
import re
import unicodedata
import urllib.request
import urllib.error

BASE = Path(__file__).resolve().parent
ARTICLE_DIR = BASE / "makaleler"
QA_FILE = BASE / "ogrettiklerim.json"
ENV_FILE = BASE / ".env"
MAX_HISTORY = 12

STOP = set("""
ve veya ile ama icin gibi bir bu su o da de mi mu nasil ne kim nerede neden
hangi kac benim senin onun ben sen biz siz onlar olan olarak daha cok az
ise ya ki her zaman sonra once hakkinda nedir eder misin misin misiniz
""".split())

def norm(text):
    text = text.lower().translate(str.maketrans({
        "ı":"i", "ş":"s", "ğ":"g", "ü":"u", "ö":"o", "ç":"c"
    }))
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))

def tokens(text):
    return [w for w in re.findall(r"[a-z0-9_]+", norm(text))
            if len(w) > 1 and w not in STOP]

def load_dotenv():
    # .env is optional. Never prints or exposes the API key.
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip("\"' ")
            if key and value and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass

class DataDevAI:
    def __init__(self):
        load_dotenv()
        self.docs = []
        self.learned = []
        self.history = []
        self.use_cloud = True
        self.reload()

    def api_config(self):
        key = os.getenv("DATADEV_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base = os.getenv("DATADEV_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("DATADEV_AI_MODEL", "gpt-4.1-mini")
        return key, base, model

    def reload(self):
        self.docs = []
        ARTICLE_DIR.mkdir(exist_ok=True)
        for file in sorted(ARTICLE_DIR.glob("*.txt")):
            try:
                text = file.read_text(encoding="utf-8-sig")
            except Exception:
                continue
            title = file.stem.replace("_", " ")
            heading = title
            for block in re.split(r"\n\s*\n", text):
                block = block.strip()
                if not block:
                    continue
                lines = block.splitlines()
                if len(lines) == 1 and len(lines[0]) < 90 and lines[0].upper() == lines[0]:
                    heading = lines[0].strip()
                    continue
                paragraph = " ".join(line.strip() for line in lines)
                self.docs.append({
                    "source": file.name, "heading": heading, "text": paragraph,
                    "words": set(tokens(heading + " " + paragraph))
                })
        try:
            self.learned = json.loads(QA_FILE.read_text(encoding="utf-8"))
            if not isinstance(self.learned, list):
                self.learned = []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.learned = []
        return len(self.docs)

    def best_context(self, question, limit=3):
        qwords = set(tokens(question))
        if not qwords:
            return []
        ranked = []
        for item in self.docs:
            overlap = qwords & item["words"]
            if not overlap:
                continue
            heading_words = set(tokens(item["heading"] + " " + item["source"].replace("_", " ")))
            # Reward query coverage and topic matches; penalize unrelated long paragraphs.
            coverage = len(overlap) / len(qwords)
            precision = len(overlap) / max(1, len(item["words"]))
            score = 0.72 * coverage + 0.20 * len(qwords & heading_words) + 0.08 * precision
            ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        if not ranked or ranked[0][0] < 0.18:
            return []
        result = []
        for score, item in ranked[:limit]:
            if score < max(0.12, ranked[0][0] * 0.42):
                continue
            result.append((score, item))
        return result

    def api_answer(self, question):
        key, base, model = self.api_config()
        if not key or not self.use_cloud:
            return None
        context = self.best_context(question)
        context_text = "\n\n".join(
            f"[Kaynak: {item['source']} — {item['heading']}]\n{item['text']}"
            for _, item in context
        )
        system = (
            "Sen DataDev AI adında, ChatGPT tarzında yardımcı bir asistansın. "
            "Kullanıcıyla doğal, sıcak ve açık Türkçe konuş; soruya doğrudan cevap ver. "
            "Gereksiz yere soru sorma. Bilmediğin bir şeyi kesinmiş gibi uydurma; "
            "belirsizliği açıkça söyle. Kod istenirse çalışır ve eksiksiz kod vermeye çalış. "
            "Kullanıcının yerel makaleleri aşağıda verilmişse, ilgili olduklarında bunlardan yararlan "
            "ama alakasız metni cevaba zorla ekleme. Makale bilgisini kullandığında kaynak adını belirt. "
            "Güvenlik açısından riskli isteklerde güvenli davran."
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(self.history[-MAX_HISTORY:])
        user_message = question
        if context_text:
            user_message += "\n\nYerel bilgi tabanı (yalnızca ilgiliyse kullan):\n" + context_text[:10000]
        messages.append({"role": "user", "content": user_message})
        body = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            base + "/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
            answer = data["choices"][0]["message"]["content"].strip()
            if answer:
                self.history.extend([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer}
                ])
                self.history = self.history[-MAX_HISTORY:]
                return answer
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return "API anahtarı kabul edilmedi. .env dosyasındaki anahtarı kontrol et."
            if e.code == 429:
                return "API kullanım sınırına veya bakiyeye ulaşıldı. Hesap ve API faturalandırmasını kontrol et."
            return f"Çevrim içi yapay zekâ isteği başarısız oldu (HTTP {e.code}). Yerel bilgi tabanına geçiyorum."
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError):
            return "Çevrim içi yapay zekâya bağlanamadım. Yerel bilgi tabanına geçiyorum."
        return None

    def answer(self, question):
        q = norm(question).strip(" .!?")
        if q in {"adin ne", "ismin ne", "sen kimsin"}:
            return "Ben DataDev AI'yim. Çevrim içi model ayarlanırsa sohbet bağlamını hatırlayan bir asistan olarak, ayarlanmazsa yerel makalelerle çalışırım."
        if any(g in q for g in ("selam", "merhaba", "hey", "sa")) and len(q.split()) <= 4:
            return "Selam! Ben DataDev AI. Nasıl yardımcı olayım?"
        if "nasilsin" in q or "naber" in q:
            return "İyiyim, teşekkürler! Sen nasılsın?"
        if any(p in q for p in ("tesekkur", "sag ol", "eyvallah")):
            return "Rica ederim! Başka bir şeyde de yardımcı olabilirim."
        online = self.api_answer(question)
        if online:
            return online

        qwords = set(tokens(question))
        best, best_score = None, 0.0
        for item in self.learned:
            qw = set(tokens(item.get("question", "")))
            if not qw:
                continue
            overlap = len(qwords & qw)
            score = overlap / max(1, len(qwords | qw))
            if norm(item.get("question", "")).strip(" .!?") == q:
                score = 2.0
            if score > best_score:
                best, best_score = ("learned", item), score
        if best and best_score >= 0.25:
            return best[1].get("answer", "Bu soruya kayıtlı yanıt yok.")

        contexts = self.best_context(question, limit=1)
        if contexts:
            item = contexts[0][1]
            return item["text"] + "\n\nKaynak: " + item["source"] + " — " + item["heading"]
        return ("Şu anda çevrim içi model bağlı değil ve yerel makalelerimde bu soruya uygun bilgi bulamadım. "
                ".env dosyasına API ayarı ekleyebilir veya makaleler klasörüne ilgili bir .txt dosyası koyabilirsin.")

    def teach(self, raw):
        if "|" not in raw:
            return "Kullanım: /ogret soru | cevap"
        question, answer = raw.split("|", 1)
        question, answer = question.strip(), answer.strip()
        if not question or not answer:
            return "Soru ve cevap boş olamaz."
        normalized = norm(question).strip(" .!?")
        for item in self.learned:
            if norm(item.get("question", "")).strip(" .!?") == normalized:
                item["answer"], item["question"] = answer, question
                break
        else:
            self.learned.append({"question": question, "answer": answer})
        QA_FILE.write_text(json.dumps(self.learned, ensure_ascii=False, indent=2), encoding="utf-8")
        return "Öğrendim ve kaydettim."

def main():
    print("=" * 60)
    print("                    DATADEV AI")
    print("       SOHBET ASISTANI + YEREL BILGI TABANI")
    print("=" * 60)
    ai = DataDevAI()
    key, _, model = ai.api_config()
    mode = f"Çevrim içi model: {model}" if key else "Yerel mod: API anahtarı ayarlanmamış"
    print(f"{len(ai.docs)} makale bölümü ve {len(ai.learned)} öğrenilmiş kayıt yüklendi.")
    print(mode)
    print("Komutlar: /yardim, /kaynaklar, /yenile, /ogret soru | cevap, /ogrettiklerim, /mod, /sifirla, /cikis\n")
    while True:
        try:
            question = input("Sen > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDataDev AI kapatılıyor.")
            break
        if not question:
            continue
        low = norm(question)
        if low in {"/cikis", "/exit", "exit", "quit"}:
            print("DataDev AI > Görüşürüz!")
            break
        if low == "/yardim":
            print("DataDev AI komutları:")
            print("  /kaynaklar              Makale kaynaklarını listeler")
            print("  /yenile                 Makaleleri yeniden okur")
            print("  /ogret soru | cevap     Kendi soru-cevap bilginizi kaydeder")
            print("  /ogrettiklerim          Kayıt sayısını gösterir")
            print("  /mod                    Çevrim içi/yerel çalışma durumunu gösterir")
            print("  /sifirla                Bu sohbetin kısa süreli belleğini temizler")
            print("  /cikis                  Çıkış\n")
            continue
        if low == "/kaynaklar":
            files = sorted(ARTICLE_DIR.glob("*.txt"))
            print("DataDev AI > Makale kaynakları:")
            for file in files:
                print("  - " + file.name)
            if not files:
                print("  Henüz .txt makalesi yok.")
            print()
            continue
        if low == "/yenile":
            print(f"DataDev AI > {ai.reload()} bölüm ve {len(ai.learned)} kayıt yüklendi.\n")
            continue
        if low == "/ogrettiklerim":
            print(f"DataDev AI > {len(ai.learned)} kayıtlı soru-cevap var.\n")
            continue
        if low == "/mod":
            key, _, model = ai.api_config()
            print("DataDev AI > " + (f"Çevrim içi: {model}" if key and ai.use_cloud else "Yerel bilgi tabanı modu") + "\n")
            continue
        if low == "/sifirla":
            ai.history.clear()
            print("DataDev AI > Bu sohbetin kısa süreli belleği temizlendi.\n")
            continue
        if low.startswith("/ogret "):
            print("DataDev AI > " + ai.teach(question[7:]) + "\n")
            continue
        print("DataDev AI > " + ai.answer(question) + "\n")

if __name__ == "__main__":
    main()
