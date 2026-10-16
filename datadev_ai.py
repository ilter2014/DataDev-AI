# -*- coding: utf-8 -*-
"""
DataDev AI 0.1
Kendi parametrelerini sifirdan egiten kucuk karakter tabanli sinir agi.

Kurulum:
    python -m pip install numpy

Calistirma:
    python datadev_ai.py

Kendi egitim verilerini ayni klasordeki data.txt dosyasina ekleyebilirsin.
"""

from pathlib import Path
import json
import sys
import numpy as np

# Windows CMD'nin kod sayfasinda bulunmayan karakterler yuzunden program kapanmasin.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data.txt"
ARTICLE_DIR = PROJECT_DIR / "makaleler"
MODEL_FILE = PROJECT_DIR / "datadev_ai_model.npz"
VOCAB_FILE = PROJECT_DIR / "datadev_ai_vocab.json"

CONTEXT_SIZE = 8
EMBED_SIZE = 16
HIDDEN_SIZE = 64
EPOCHS = 12
LEARNING_RATE = 0.01
BATCH_SIZE = 256
SEED = 42

STARTER_TEXT = """
merhaba
merhaba nasilsin
iyiyim tesekkur ederim
ben datadev ai
datadev ai ogreniyor
datadev ai bir yapay zeka projesidir
yapay zeka verilerden ogrenir
model egitim yaparak ogrenebilir
python bir programlama dilidir
kod yazmayi seviyorum
ben kod yazabilirim
nasilsin ben iyiyim
veri kaliteli olursa model daha iyi ogrenebilir
bilgisayar kod calistirir
ben yeni seyler ogreniyorum
datadev ai gelistiriliyor
"""

def load_text():
    parts = [STARTER_TEXT]
    if DATA_FILE.exists():
        extra = DATA_FILE.read_text(encoding="utf-8")
        if extra.strip():
            parts.append(extra)
            print(f"Ek egitim verisi okundu: {DATA_FILE.name}")
    if ARTICLE_DIR.exists():
        articles = sorted(ARTICLE_DIR.glob("*.txt"))
        for article in articles:
            try:
                content = article.read_text(encoding="utf-8-sig")
                if content.strip():
                    parts.append("\n" + article.stem.replace("_", " ") + "\n" + content)
            except (OSError, UnicodeError) as exc:
                print(f"Uyari: {article.name} okunamadi: {exc}")
        print(f"Makale egitim verisi: {len(articles)} dosya")
    text = "\n".join(parts).lower()
    print(f"Toplam egitim metni: {len(text):,} karakter")
    return text

def softmax(logits):
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(logits)
    return exp_values / np.sum(exp_values, axis=1, keepdims=True)

class DataDevAI:
    def __init__(self, text):
        self.chars = sorted(set(text))
        self.char_to_id = {ch: i for i, ch in enumerate(self.chars)}
        self.id_to_char = {i: ch for i, ch in enumerate(self.chars)}
        self.vocab_size = len(self.chars)
        rng = np.random.default_rng(SEED)

        self.E = rng.normal(0, 0.08, (self.vocab_size, EMBED_SIZE))
        input_size = CONTEXT_SIZE * EMBED_SIZE
        self.W1 = rng.normal(0, np.sqrt(2 / input_size),
                             (input_size, HIDDEN_SIZE))
        self.b1 = np.zeros((1, HIDDEN_SIZE))
        self.W2 = rng.normal(0, np.sqrt(2 / HIDDEN_SIZE),
                             (HIDDEN_SIZE, self.vocab_size))
        self.b2 = np.zeros((1, self.vocab_size))
        self.params = [self.E, self.W1, self.b1, self.W2, self.b2]
        self.m = [np.zeros_like(p) for p in self.params]
        self.v = [np.zeros_like(p) for p in self.params]
        self.step = 0
        self.rng = np.random.default_rng(SEED + 7)

    def make_examples(self, text):
        ids = [self.char_to_id[c] for c in text if c in self.char_to_id]
        xs, ys = [], []
        for i in range(CONTEXT_SIZE, len(ids)):
            xs.append(ids[i - CONTEXT_SIZE:i])
            ys.append(ids[i])
        if not xs:
            raise ValueError("Egitim metni cok kisa.")
        return np.asarray(xs, dtype=np.int64), np.asarray(ys, dtype=np.int64)

    def forward(self, contexts):
        embedded = self.E[contexts]
        flat = embedded.reshape(len(contexts), -1)
        hidden = np.tanh(flat @ self.W1 + self.b1)
        probs = softmax(hidden @ self.W2 + self.b2)
        return probs, flat, hidden

    def train(self, text):
        x, y = self.make_examples(text)
        print(f"Sozluk karakteri: {self.vocab_size}")
        print(f"Egitim ornegi: {len(y)}")
        print(f"Baglam: {CONTEXT_SIZE} karakter | Gizli noron: {HIDDEN_SIZE}")
        print("DataDev AI sifirdan egitiliyor...")

        order_rng = np.random.default_rng(SEED + 1)
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        for epoch in range(1, EPOCHS + 1):
            order = order_rng.permutation(len(y))
            total_loss = 0.0
            seen = 0

            for start in range(0, len(y), BATCH_SIZE):
                batch = order[start:start + BATCH_SIZE]
                xb, yb = x[batch], y[batch]
                probs, flat, hidden = self.forward(xb)
                n = len(yb)
                selected = np.clip(probs[np.arange(n), yb], 1e-12, 1.0)
                total_loss += float(-np.sum(np.log(selected)))
                seen += n

                dlogits = probs.copy()
                dlogits[np.arange(n), yb] -= 1
                dlogits /= n
                dW2 = hidden.T @ dlogits
                db2 = np.sum(dlogits, axis=0, keepdims=True)
                dhidden = (dlogits @ self.W2.T) * (1 - hidden ** 2)
                dW1 = flat.T @ dhidden
                db1 = np.sum(dhidden, axis=0, keepdims=True)
                dflat = dhidden @ self.W1.T
                dembed = dflat.reshape(n, CONTEXT_SIZE, EMBED_SIZE)
                dE = np.zeros_like(self.E)
                np.add.at(dE, xb.reshape(-1), dembed.reshape(-1, EMBED_SIZE))
                grads = [dE, dW1, db1, dW2, db2]

                self.step += 1
                for i, (param, grad) in enumerate(zip(self.params, grads)):
                    self.m[i] = beta1 * self.m[i] + (1 - beta1) * grad
                    self.v[i] = beta2 * self.v[i] + (1 - beta2) * grad * grad
                    m_hat = self.m[i] / (1 - beta1 ** self.step)
                    v_hat = self.v[i] / (1 - beta2 ** self.step)
                    param -= LEARNING_RATE * m_hat / (np.sqrt(v_hat) + eps)

            if epoch == 1 or epoch % 10 == 0 or epoch == EPOCHS:
                print(f"Epoch {epoch:3d}/{EPOCHS} | Loss: {total_loss / seen:.4f}")

        print("Egitim tamamlandi.")

    def generate(self, start="merhaba", length=160, temperature=0.8):
        if temperature <= 0:
            raise ValueError("temperature sifirdan buyuk olmali.")
        start = (start or "m").lower()
        result = start
        ids = [self.char_to_id.get(c, 0) for c in start]
        context = ([0] * CONTEXT_SIZE + ids)[-CONTEXT_SIZE:]

        for _ in range(length):
            probs, _, _ = self.forward(np.asarray([context], dtype=np.int64))
            logits = np.log(np.clip(probs[0], 1e-12, 1.0)) / temperature
            logits -= np.max(logits)
            next_probs = np.exp(logits)
            next_probs /= next_probs.sum()
            next_id = int(self.rng.choice(self.vocab_size, p=next_probs))
            result += self.id_to_char[next_id]
            context = context[1:] + [next_id]
        return result

    def save(self):
        np.savez(MODEL_FILE, E=self.E, W1=self.W1, b1=self.b1,
                 W2=self.W2, b2=self.b2)
        VOCAB_FILE.write_text(
            json.dumps(self.chars, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Model agirliklari kaydedildi: {MODEL_FILE.name}")
        print(f"Sozluk kaydedildi: {VOCAB_FILE.name}")

def main():
    print("=" * 54)
    print("                    DATADEV AI")
    print("             Kendi yapay zeka modelimiz")
    print("=" * 54)
    text = load_text()
    model = DataDevAI(text)
    model.train(text)
    model.save()
    print("\nDataDev AI metin uretim testi:")
    print("-" * 54)
    print(model.generate(start="datadev ai", length=180))
    print("-" * 54)
    print("Not: Bu ilk prototiptir; genel bilgisi veya akici sohbet yetenegi yoktur.")
    print("Yeni egitim metinleri icin data.txt dosyasi kullan.")

if __name__ == "__main__":
    main()
