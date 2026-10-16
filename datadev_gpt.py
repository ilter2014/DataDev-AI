# -*- coding: utf-8 -*-
"""DataDev GPT: a small decoder-only Transformer trained locally from scratch.
This is an educational miniature GPT, not a ChatGPT-scale pretrained model.
"""
from pathlib import Path
import argparse, json, math, os, random, sys, time
import torch
from torch import nn
import torch.nn.functional as F

BASE = Path(__file__).resolve().parent
ARTICLES = BASE / "makaleler"
DATA_FILE = BASE / "data.txt"
MODEL_FILE = BASE / "datadev_gpt_model.pt"
VOCAB_FILE = BASE / "datadev_gpt_vocab.json"
LOG_FILE = BASE / "datadev_gpt_train.log"

# Be polite to the PC while Roblox is running.
torch.set_num_threads(1)
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass

SEED = 2026
BLOCK_SIZE = 96
BATCH_SIZE = 8
N_EMBD = 96
N_HEAD = 4
N_LAYER = 2
DROPOUT = 0.08
STEPS = 1200
LEARNING_RATE = 0.0005
DEVICE = torch.device("cpu")

STARTER = """
Kullanıcı: Merhaba!
DataDev AI: Merhaba! Ben DataDev AI. Sana nasıl yardımcı olabilirim?
Kullanıcı: Nasılsın?
DataDev AI: İyiyim, teşekkür ederim. Sen nasılsın?
Kullanıcı: Adın ne?
DataDev AI: Ben DataDev AI, yerel bilgisayarda eğitilen küçük bir dil modeli prototipiyim.
Kullanıcı: Yapay zeka nedir?
DataDev AI: Yapay zeka, bilgisayarların verilerden örüntüler öğrenerek tahmin, sınıflandırma ve metin üretme gibi görevleri yapmasını sağlayan yöntemler alanıdır.
Kullanıcı: Python nedir?
DataDev AI: Python, okunabilir sözdizimine sahip genel amaçlı bir programlama dilidir. Otomasyon, web geliştirme, veri analizi ve yapay zeka projelerinde kullanılır.
Kullanıcı: Makine öğrenmesi nedir?
DataDev AI: Makine öğrenmesi, bilgisayarların örneklerden örüntüler öğrenmesini sağlayan yapay zeka yaklaşımıdır.
Kullanıcı: Bir şeyi bilmiyorsan ne yaparsın?
DataDev AI: Emin olmadığım konularda kesin konuşmamaya çalışırım. Bu küçük modelin bilgisi sınırlıdır ve hata yapabilir.
"""

def corpus_text():
    pieces = [STARTER]
    if DATA_FILE.exists():
        try:
            pieces.append(DATA_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
    if ARTICLES.exists():
        for path in sorted(ARTICLES.glob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8-sig").strip()
                if text:
                    pieces.append("\n\n[Makale: " + path.stem.replace("_", " ") + "]\n" + text)
                    # Add small question/answer-shaped examples from headings and paragraphs.
                    for block in text.split("\n\n"):
                        block = " ".join(x.strip() for x in block.splitlines()).strip()
                        if 35 <= len(block) <= 500:
                            pieces.append("\nKullanıcı: Bu konuda bilgi ver.\nDataDev AI: " + block)
            except Exception:
                continue
    return "\n".join(pieces)

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
        b, t = idx.shape
        positions = torch.arange(t, device=idx.device)
        x = self.token_emb(idx) + self.pos_emb(positions)[None, :, :]
        mask = torch.triu(torch.ones(t, t, device=idx.device, dtype=torch.bool), diagonal=1)
        x = self.blocks(x, mask=mask)
        logits = self.lm_head(self.norm(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens=240, temperature=0.8, top_k=24):
        self.eval()
        for _ in range(max_new_tokens):
            crop = idx[:, -BLOCK_SIZE:]
            logits, _ = self(crop)
            logits = logits[:, -1, :] / max(temperature, 0.05)
            k = min(top_k, logits.size(-1))
            values, _ = torch.topk(logits, k)
            logits[logits < values[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, nxt), dim=1)
        return idx

def train():
    random.seed(SEED)
    torch.manual_seed(SEED)
    text = corpus_text()
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = chars
    ids = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    if len(ids) < BLOCK_SIZE + 2:
        raise RuntimeError("Eğitim metni çok kısa.")
    split = max(BLOCK_SIZE + 1, int(len(ids) * 0.94))
    train_ids, val_ids = ids[:split], ids[split:]
    if len(val_ids) < BLOCK_SIZE + 2:
        val_ids = train_ids[-(BLOCK_SIZE+2):]

    def batch(source):
        max_start = len(source) - BLOCK_SIZE - 1
        starts = torch.randint(max(1, max_start), (BATCH_SIZE,))
        x = torch.stack([source[int(i):int(i)+BLOCK_SIZE] for i in starts])
        y = torch.stack([source[int(i)+1:int(i)+BLOCK_SIZE+1] for i in starts])
        return x.to(DEVICE), y.to(DEVICE)

    model = TinyGPT(len(chars)).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    params = sum(p.numel() for p in model.parameters())
    print("DataDev GPT — sıfırdan Transformer eğitimi", flush=True)
    print(f"Veri: {len(text):,} karakter | sözlük: {len(chars)} karakter | parametre: {params:,}", flush=True)
    print(f"Cihaz: {DEVICE} | CPU iş parçacığı: 1 | eğitim adımı: {STEPS}", flush=True)
    print("Roblox etkisini azaltmak için düşük öncelikte çalışıyor.", flush=True)
    start = time.time()
    model.train()
    for step in range(1, STEPS + 1):
        xb, yb = batch(train_ids)
        _, loss = model(xb, yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step == 1 or step % 30 == 0 or step == STEPS:
            model.eval()
            with torch.no_grad():
                vx, vy = batch(val_ids)
                _, vloss = model(vx, vy)
            model.train()
            elapsed = time.time() - start
            line = f"Adım {step:3d}/{STEPS} | eğitim loss {loss.item():.3f} | doğrulama loss {vloss.item():.3f} | {elapsed:.1f} sn"
            print(line, flush=True)
            with LOG_FILE.open("a", encoding="utf-8") as log:
                log.write(line + "\n")
    torch.save({
        "model": model.state_dict(), "chars": chars,
        "config": {"block_size": BLOCK_SIZE, "n_embd": N_EMBD, "n_head": N_HEAD,
                   "n_layer": N_LAYER, "steps": STEPS, "params": params}
    }, MODEL_FILE)
    VOCAB_FILE.write_text(json.dumps(chars, ensure_ascii=False), encoding="utf-8")
    print(f"EĞİTİM TAMAMLANDI — model kaydedildi: {MODEL_FILE.name}", flush=True)
    print(f"Toplam süre: {time.time()-start:.1f} sn", flush=True)
    sample = "Kullanıcı: Yapay zeka nedir?\nDataDev AI:"
    idx = torch.tensor([[stoi.get(c, 0) for c in sample]], dtype=torch.long)
    out = model.generate(idx, max_new_tokens=180, temperature=0.7)[0].tolist()
    print("\nÜRETİM TESTİ:\n" + "".join(itos[i] for i in out)[len(sample):], flush=True)

def chat():
    if not MODEL_FILE.exists():
        print("Önce modeli eğit: python datadev_gpt.py --train")
        return
    saved = torch.load(MODEL_FILE, map_location=DEVICE, weights_only=False)
    chars = saved["chars"]
    stoi = {ch: i for i, ch in enumerate(chars)}
    model = TinyGPT(len(chars)).to(DEVICE)
    model.load_state_dict(saved["model"])
    model.eval()
    print("DataDev GPT hazır. Bu küçük model deneyseldir; /cikis ile çık.", flush=True)
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
        prompt = "Kullanıcı: " + q + "\nDataDev AI:"
        ids = [stoi.get(c, 0) for c in prompt][-BLOCK_SIZE:]
        inp = torch.tensor([ids], dtype=torch.long)
        out = model.generate(inp, max_new_tokens=240, temperature=0.75)[0].tolist()
        generated = "".join(chars[i] for i in out[len(ids):])
        answer = generated.split("\nKullanıcı:", 1)[0].strip()
        print("DataDev GPT >", answer or "(Model henüz tutarlı cevap üretemedi.)", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--train", action="store_true", help="Modeli sıfırdan eğit")
    group.add_argument("--chat", action="store_true", help="Eğitilmiş modelle sohbet et")
    args = parser.parse_args()
    if args.chat:
        chat()
    else:
        train()
