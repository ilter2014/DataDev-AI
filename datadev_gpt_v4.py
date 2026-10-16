# -*- coding: utf-8 -*-
"""DataDev GPT v4: local model with optional Groq answer review."""
from pathlib import Path
import argparse, json, math, random, re, time, os, urllib.request, urllib.error
import torch
from torch import nn
import torch.nn.functional as F

BASE = Path(__file__).resolve().parent
ARTICLES = BASE / "makaleler"
BOOKS = BASE / "kitaplar"
DATA_FILE = BASE / "data.txt"
MODEL_FILE = BASE / "datadev_gpt_v4_model.pt"
VOCAB_FILE = BASE / "datadev_gpt_v4_vocab.json"
LOG_FILE = BASE / "datadev_gpt_v4_train.log"
INTERACTION_TRAINING_FILE = BASE / "datadev_interaction_training.jsonl"
USER_LEARNING_FILE = BASE / "datadev_user_learning.jsonl"
GROQ_KEY_FILE = BASE / "groq_api_key.txt"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# Keep CPU use low so the PC remains usable for other applications.
torch.set_num_threads(1)
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass

SEED = 2026
BLOCK_SIZE = 128
BATCH_SIZE = 8
N_EMBD = 96
N_HEAD = 4
N_LAYER = 2
DROPOUT = 0.08
STEPS = 1200
LEARNING_RATE = 0.00035
EVAL_INTERVAL = 30
EVAL_BATCHES = 4
DEVICE = torch.device("cpu")

STARTER = [
    ("Merhaba!", "Merhaba! Ben DataDev AI. Sana nasıl yardımcı olabilirim?"),
    ("Nasılsın?", "İyiyim, teşekkür ederim. Sen nasılsın?"),
    ("Adın ne?", "Ben DataDev AI. Yerel bilgisayarda sıfırdan eğitilen küçük bir dil modeli prototipiyim."),
    ("Yapay zeka nedir?", "Yapay zeka, bilgisayarların metin işleme, örüntü bulma, tahmin ve içerik üretme gibi görevleri yapmasını sağlayan yöntemler alanıdır."),
    ("Python nedir?", "Python, okunabilir sözdizimine sahip genel amaçlı bir programlama dilidir. Otomasyon, web geliştirme, veri analizi ve yapay zekâ projelerinde kullanılır."),
    ("Makine öğrenmesi nedir?", "Makine öğrenmesi, bilgisayarların örneklerden istatistiksel örüntüler öğrenmesini sağlayan yapay zekâ yaklaşımıdır."),
    ("Bir şeyi bilmiyorsan ne yaparsın?", "Emin olmadığım konularda kesin konuşmamaya çalışırım. Bilgim sınırlı olabilir ve hata yapabilirim."),
    ("Dil modeli nasıl öğrenir?", "Dil modeli, eğitim verisindeki karakter veya token örüntülerini öğrenir. Eğitim sırasında tahmin hatası hesaplanır ve modelin parametreleri güncellenir."),
]

def split_article(path):
    raw = path.read_text(encoding="utf-8-sig").strip()
    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
    if not blocks:
        return []
    title = raw.splitlines()[0].strip(" #")
    examples = []
    section = title
    for i, block in enumerate(blocks[1:], 1):
        block = block.strip()
        if len(block) < 30:
            section = block.strip(" #:")
            continue
        # Most article subheadings are short, uppercase lines; keep them as context.
        if len(block) < 90 and block.upper() == block and any(ch.isalpha() for ch in block):
            section = block.strip(" #:")
            continue
        question = f"{title} konusunda {section} hakkında bilgi ver."
        if section == title:
            question = f"{title} nedir? Açıkla."
        examples.append((question, block))
    if not examples and len(raw) > 30:
        examples.append((f"{title} nedir? Açıkla.", raw))
    return examples

def build_corpus():
    examples = list(STARTER)
    article_paths = sorted((list(ARTICLES.glob("*.txt")) if ARTICLES.exists() else []) + (list(BOOKS.glob("*.txt")) if BOOKS.exists() else []))
    # Split whole source files, not adjacent characters, to reduce train/validation leakage.
    rng = random.Random(SEED)
    rng.shuffle(article_paths)
    val_count = max(2, round(len(article_paths) * 0.12)) if len(article_paths) >= 10 else 1
    val_paths = set(article_paths[:val_count])
    train_examples = list(examples)
    # Only manually approved interaction examples are eligible for future training.
    if INTERACTION_TRAINING_FILE.exists():
        try:
            for line in INTERACTION_TRAINING_FILE.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    q = item.get("question")
                    a = item.get("answer")
                    if isinstance(q, str) and isinstance(a, str) and q.strip() and a.strip():
                        train_examples.append((q.strip(), a.strip()))
                except (json.JSONDecodeError, AttributeError):
                    continue
        except (OSError, UnicodeError):
            pass
    # User corrections/approvals are included only after explicit human approval.
    if USER_LEARNING_FILE.exists():
        try:
            for line in USER_LEARNING_FILE.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    q, a = item.get("question"), item.get("answer")
                    if item.get("human_approved") is True and item.get("training_eligible") is True and isinstance(q, str) and isinstance(a, str) and q.strip() and a.strip():
                        train_examples.append((q.strip(), a.strip()))
                except (json.JSONDecodeError, AttributeError):
                    continue
        except (OSError, UnicodeError):
            pass

    # Groq-created lesson material is training-only: it is never used as a direct retrieval answer.
    curriculum_file = BASE / "datadev_curriculum_training.jsonl"
    if curriculum_file.exists():
        try:
            for line in curriculum_file.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    q, a = item.get("question"), item.get("answer")
                    if isinstance(q, str) and isinstance(a, str) and q.strip() and a.strip():
                        train_examples.append((q.strip(), a.strip()))
                except (json.JSONDecodeError, AttributeError):
                    continue
        except (OSError, UnicodeError):
            pass
    val_examples = []
    for path in article_paths:
        try:
            pairs = split_article(path)
        except (OSError, UnicodeError):
            continue
        (val_examples if path in val_paths else train_examples).extend(pairs)

    # Optional user-provided text is treated as training material only.
    if DATA_FILE.exists():
        try:
            extra = DATA_FILE.read_text(encoding="utf-8-sig").strip()
            if extra:
                train_examples.append(("Ek eğitim metni hakkında bilgi ver.", extra))
        except (OSError, UnicodeError):
            pass

    def serialize(pairs):
        return "\n\n".join(f"Kullanıcı: {q}\nDataDev AI: {a}" for q, a in pairs) + "\n\n"
    return serialize(train_examples), serialize(val_examples), len(article_paths), len(train_examples), len(val_examples)

class TinyGPT(nn.Module):
    def __init__(self, vocab_size):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, N_EMBD)
        self.pos_emb = nn.Embedding(BLOCK_SIZE, N_EMBD)
        layer = nn.TransformerEncoderLayer(
            d_model=N_EMBD, nhead=N_HEAD, dim_feedforward=4*N_EMBD,
            dropout=DROPOUT, batch_first=True, norm_first=True, activation="gelu"
        )
        self.blocks = nn.TransformerEncoder(layer, num_layers=N_LAYER, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(N_EMBD)
        self.lm_head = nn.Linear(N_EMBD, vocab_size, bias=False)
        self.lm_head.weight = self.token_emb.weight
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if isinstance(module, nn.Linear) and module.bias is not None:
                nn.init.zeros_(module.bias)

    def forward(self, idx, targets=None):
        _, t = idx.shape
        pos = torch.arange(t, device=idx.device)
        x = self.token_emb(idx) + self.pos_emb(pos)[None, :, :]
        mask = torch.triu(torch.ones(t, t, device=idx.device, dtype=torch.bool), diagonal=1)
        x = self.blocks(x, mask=mask)
        logits = self.lm_head(self.norm(x))
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1)) if targets is not None else None
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens=220, temperature=0.65, top_k=12):
        self.eval()
        for _ in range(max_new_tokens):
            crop = idx[:, -BLOCK_SIZE:]
            logits, _ = self(crop)
            logits = logits[:, -1, :] / max(temperature, 0.05)
            k = min(top_k, logits.size(-1))
            vals, _ = torch.topk(logits, k)
            logits[logits < vals[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, nxt), dim=1)
        return idx

def make_batches(source, count, rng):
    max_start = len(source) - BLOCK_SIZE - 1
    if max_start < 1:
        raise RuntimeError("Eğitim/doğrulama metni BLOCK_SIZE için çok kısa.")
    starts = [rng.randrange(max_start) for _ in range(count * BATCH_SIZE)]
    batches = []
    for j in range(count):
        ss = starts[j*BATCH_SIZE:(j+1)*BATCH_SIZE]
        x = torch.stack([source[s:s+BLOCK_SIZE] for s in ss])
        y = torch.stack([source[s+1:s+BLOCK_SIZE+1] for s in ss])
        batches.append((x, y))
    return batches

@torch.no_grad()
def evaluate(model, batches):
    model.eval()
    losses = []
    for x, y in batches:
        _, loss = model(x, y)
        losses.append(loss.item())
    model.train()
    return sum(losses) / len(losses)

def train():
    random.seed(SEED)
    torch.manual_seed(SEED)
    train_text, val_text, n_articles, n_train_examples, n_val_examples = build_corpus()
    # Build a shared character vocabulary from the source text.
    chars = sorted(set(train_text + val_text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    train_ids = torch.tensor([stoi[c] for c in train_text], dtype=torch.long)
    val_ids = torch.tensor([stoi[c] for c in val_text], dtype=torch.long)
    if len(train_ids) < BLOCK_SIZE + 2 or len(val_ids) < BLOCK_SIZE + 2:
        raise RuntimeError(f"Veri çok kısa: eğitim={len(train_ids)}, doğrulama={len(val_ids)} karakter.")

    val_batches = make_batches(val_ids, EVAL_BATCHES, random.Random(SEED + 1))
    train_rng = random.Random(SEED + 2)
    model = TinyGPT(len(chars)).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.02)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=STEPS, eta_min=LEARNING_RATE * 0.15)
    params = sum(p.numel() for p in model.parameters())
    print("DataDev GPT v3 — kitaplarla genişletilmiş eğitim", flush=True)
    print(f"Kaynak dosyası (makale + kitap): {n_articles} | eğitim örneği: {n_train_examples} | doğrulama örneği: {n_val_examples}", flush=True)
    print(f"Karakter: eğitim {len(train_ids):,} / doğrulama {len(val_ids):,} | sözlük: {len(chars)} | parametre: {params:,}", flush=True)
    print(f"Bağlam: {BLOCK_SIZE} karakter | adım: {STEPS} | CPU tek iş parçacığı, düşük öncelik", flush=True)
    start = time.time()
    best_val = float("inf")
    best_step = 0
    LOG_FILE.write_text("", encoding="utf-8")
    model.train()
    for step in range(1, STEPS + 1):
        start_idx = train_rng.randrange(len(train_ids) - BLOCK_SIZE - 1)
        starts = [train_rng.randrange(len(train_ids) - BLOCK_SIZE - 1) for _ in range(BATCH_SIZE)]
        xb = torch.stack([train_ids[s:s+BLOCK_SIZE] for s in starts])
        yb = torch.stack([train_ids[s+1:s+BLOCK_SIZE+1] for s in starts])
        _, loss = model(xb, yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        scheduler.step()
        if step == 1 or step % EVAL_INTERVAL == 0 or step == STEPS:
            vloss = evaluate(model, val_batches)
            improved = vloss < best_val
            if improved:
                best_val, best_step = vloss, step
                torch.save({
                    "model": model.state_dict(), "chars": chars,
                    "config": {"block_size": BLOCK_SIZE, "n_embd": N_EMBD, "n_head": N_HEAD,
                               "n_layer": N_LAYER, "steps": step, "params": params, "best_val": best_val}
                }, MODEL_FILE)
                VOCAB_FILE.write_text(json.dumps(chars, ensure_ascii=False), encoding="utf-8")
            line = (f"Adım {step:4d}/{STEPS} | eğitim loss {loss.item():.3f} | "
                    f"doğrulama loss {vloss:.3f} | en iyi {best_val:.3f} (adım {best_step}) | "
                    f"lr {scheduler.get_last_lr()[0]:.6f} | {time.time()-start:.1f} sn")
            print(line, flush=True)
            with LOG_FILE.open("a", encoding="utf-8") as log:
                log.write(line + "\n")

    saved = torch.load(MODEL_FILE, map_location=DEVICE, weights_only=False)
    model.load_state_dict(saved["model"])
    sample = "Kullanıcı: Yapay zeka nedir?\nDataDev AI:"
    inp = torch.tensor([[stoi.get(c, 0) for c in sample][-BLOCK_SIZE:]], dtype=torch.long)
    out = model.generate(inp, max_new_tokens=180, temperature=0.55, top_k=8)[0].tolist()
    decoded = "".join(chars[i] for i in out)
    answer = decoded.split("DataDev AI:", 1)[-1].split("\nKullanıcı:", 1)[0].strip()
    print(f"EĞİTİM BİTTİ — en iyi model {best_step}. adımda kaydedildi; doğrulama loss {best_val:.3f}.", flush=True)
    print("ÜRETİM TESTİ: " + answer, flush=True)

STOP_WORDS = set("ve veya ile ama için gibi bir bu şu o da de mi mu nasıl ne kim nerede neden hangi kaç benim senin onun ben sen biz siz onlar olan olarak daha çok az ise ya ki her zaman sonra önce hakkında nedir eder misin".split())

def normalize_words(text):
    import unicodedata
    text = text.lower().translate(str.maketrans({"ı":"i","ş":"s","ğ":"g","ü":"u","ö":"o","ç":"c"}))
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return [w for w in re.findall(r"[a-z0-9_]+", text) if len(w) > 1 and w not in STOP_WORDS]

def retrieve_local_answer(question):
    qwords = set(normalize_words(question))
    if not qwords:
        return None
    ranked = []
    for path in sorted((list(ARTICLES.glob("*.txt")) if ARTICLES.exists() else []) + (list(BOOKS.glob("*.txt")) if BOOKS.exists() else [])):
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        heading = path.stem.replace("_", " ")
        for block in re.split(r"\n\s*\n", raw):
            block = " ".join(line.strip() for line in block.splitlines()).strip()
            if not block:
                continue
            # Ignore archive metadata and boilerplate; return actual book text, not headers.
            low = block.lower()
            if (("yazar:" in low and "kaynak:" in low) or set(block) <= {"=", "-", "_", " "}
                    or any(term in low for term in ("produced by", "proofreading team", "project gutenberg", "this ebook is", "release date:", "language:"))):
                continue
            if len(block) < 90 and block.upper() == block and any(c.isalpha() for c in block):
                heading = block
                continue
            block_words = set(normalize_words(block))
            overlap = qwords & block_words
            if not overlap:
                continue
            heading_words = set(normalize_words(heading + " " + path.stem.replace("_", " ")))
            coverage = len(overlap) / len(qwords)
            heading_match = len(qwords & heading_words) / len(qwords)
            score = 0.75 * coverage + 0.25 * heading_match
            ranked.append((score, heading_match, -len(ranked), len(overlap), path.name, heading, block))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    score, heading_match, _, overlap_count, filename, heading, answer = ranked[0]
    # Avoid returning an unrelated paragraph on a single weak word match.
    if score < 0.35 or (len(qwords) >= 4 and overlap_count < 2):
        return None
    return answer + "\n\nKaynak: " + filename + " — " + heading

def get_groq_api_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key and GROQ_KEY_FILE.exists():
        try:
            key = GROQ_KEY_FILE.read_text(encoding="utf-8-sig").strip()
        except OSError:
            pass
    return key

def groq_review(question, draft, language="tr"):
    """Groq reviews/coaches the local model; its suggestion is never sent directly as the user answer."""
    api_key = get_groq_api_key()
    language = "en" if str(language).lower().startswith("en") else "tr"
    if not api_key:
        return {"status": "no_key", "decision": "KEEP", "final_answer": draft,
                "reason": "Groq API anahtarı ayarlanmamış; yerel cevap değiştirilmedi."}
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.1,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "Sen DataDev AI'nin denetçisi ve öğretmenisin; kullanıcıya doğrudan cevap veren asistan değilsin. "
                "Kullanıcının sorusunu ve DataDev'in YEREL model tarafından üretilen taslağını değerlendir. "
                "Kullanıcıya gönderilecek gerçek cevap daima yerel DataDev modelinin taslağı olarak kalır. "
                "Taslak doğru ve yeterliyse KEEP seç; değilse REPLACE seç ve final_answer alanına eğitimde örnek olarak "
                "kullanılabilecek daha doğru, açık bir öneri yaz. reason alanında taslağın neyi iyi yaptığı, hatası ve "
                "DataDev modelinin neyi öğrenmesi gerektiğini kısa ve somut anlat. Uydurma bilgi verme. "
                + ("Write the suggested correction in natural English." if language == "en" else "Türkçe, doğal ve anlaşılır yaz.")
                + " Sadece şu JSON biçiminde cevap ver: "
                '{"decision":"KEEP veya REPLACE","final_answer":"önerilen eğitim cevabı","reason":"değerlendirme ve öğrenme geri bildirimi"}.'
            )},
            {"role": "user", "content": "Kullanıcı sorusu:" + chr(10) + question + chr(10) + chr(10) + "DataDev AI taslağı:" + chr(10) + draft}
        ]
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json",
                 "User-Agent": "DataDevAI/4.0"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        result = json.loads(content)
        decision = str(result.get("decision", "KEEP")).upper()
        if decision not in {"KEEP", "REPLACE"}:
            decision = "KEEP"
        final_answer = str(result.get("final_answer", "")).strip() or draft
        reason = str(result.get("reason", "")).strip()
        return {"status": "ok", "decision": decision, "final_answer": final_answer, "reason": reason}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        return {"status": "error", "decision": "KEEP", "final_answer": draft,
                "reason": f"Groq API HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"status": "error", "decision": "KEEP", "final_answer": draft,
                "reason": f"Groq incelemesi yapılamadı: {type(e).__name__}: {e}"}

def chat():
    legacy_model = BASE / "datadev_gpt_v3_model.pt"
    active_model = MODEL_FILE if MODEL_FILE.exists() else legacy_model
    if not active_model.exists():
        print("Önce DataDev GPT v3 - Egit.bat dosyasını çalıştırıp bir modeli eğit.")
        return
    if not get_groq_api_key():
        print("UYARI: Groq API anahtarı yok. groq_api_key.txt dosyasına Groq API anahtarını koy; anahtarsız yerel mod çalışır.", flush=True)
    saved = torch.load(active_model, map_location=DEVICE, weights_only=False)
    chars = saved["chars"]
    stoi = {ch: i for i, ch in enumerate(chars)}
    model = TinyGPT(len(chars)).to(DEVICE)
    model.load_state_dict(saved["model"])
    model.eval()
    print("DataDev GPT v4 + Groq denetçisi hazır. /cikis ile çık.", flush=True)
    while True:
        try:
            q = input("Sen > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGörüşürüz!")
            break
        if not q:
            continue
        if q.lower() in {"/cikis", "/exit", "exit"}:
            break
        qnorm = " ".join(normalize_words(q))
        if qnorm in {"merhaba", "selam", "sa", "hey"}:
            draft = "Selam! Ben DataDev AI. Nasıl yardımcı olayım?"
        elif qnorm in {"adin", "ismin"} or "kimsin" in qnorm:
            draft = "Ben DataDev AI; yerel bilgisayarda eğitilen küçük bir dil modeli prototipiyim."
        else:
            grounded = retrieve_local_answer(q)
            if grounded:
                draft = grounded
            else:
                prompt = "Kullanıcı: " + q + "\nDataDev AI:"
                ids = [stoi.get(c, 0) for c in prompt][-BLOCK_SIZE:]
                inp = torch.tensor([ids], dtype=torch.long)
                out = model.generate(inp, max_new_tokens=180, temperature=0.55, top_k=8)[0].tolist()
                decoded = "".join(chars[i] for i in out)
                draft = decoded.split("DataDev AI:", 1)[-1].split("\nKullanıcı:", 1)[0].strip()
                if not draft:
                    draft = "(Yerel model henüz tutarlı bir cevap üretemedi.)"
        reviewed = groq_review(q, draft)
        if reviewed["status"] == "ok":
            print("GROQ KARARI: " + reviewed["decision"] + " — " + reviewed["reason"], flush=True)
            if reviewed["decision"] == "REPLACE":
                print("DataDev AI (Groq düzeltti) >", reviewed["final_answer"], flush=True)
            else:
                print("DataDev AI (Groq onayladı) >", reviewed["final_answer"], flush=True)
        else:
            print("GROQ DENETİMİ YOK: " + reviewed["reason"], flush=True)
            print("DataDev AI (yerel taslak) >", reviewed["final_answer"], flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", action="store_true")
    args = parser.parse_args()
    chat() if args.chat else train()
