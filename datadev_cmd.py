# -*- coding: utf-8 -*-
"""DataDev AI - CMD sohbet arayuzu."""
from pathlib import Path
import json
import numpy as np
import unicodedata

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "datadev_ai_model.npz"
VOCAB_PATH = BASE / "datadev_ai_vocab.json"
CONTEXT_SIZE = 8

def normalize(text):
    text = text.lower()
    text = text.translate(str.maketrans({
        "ı": "i", "İ": "i", "ş": "s", "ğ": "g",
        "ü": "u", "ö": "o", "ç": "c"
    }))
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))

class DataDevModel:
    def __init__(self):
        if not MODEL_PATH.exists() or not VOCAB_PATH.exists():
            raise FileNotFoundError(
                "Model dosyalari yok. Once python datadev_ai.py komutunu calistir."
            )
        self.chars = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
        self.char_to_id = {ch: i for i, ch in enumerate(self.chars)}
        self.id_to_char = {i: ch for i, ch in enumerate(self.chars)}
        with np.load(MODEL_PATH) as data:
            self.E, self.W1, self.b1 = data["E"], data["W1"], data["b1"]
            self.W2, self.b2 = data["W2"], data["b2"]
        self.rng = np.random.default_rng()

    def forward(self, context):
        embedded = self.E[np.asarray([context], dtype=np.int64)]
        hidden = np.tanh(embedded.reshape(1, -1) @ self.W1 + self.b1)
        logits = hidden @ self.W2 + self.b2
        logits -= np.max(logits, axis=1, keepdims=True)
        probs = np.exp(logits)
        return probs[0] / probs.sum()

    def reply(self, message, max_chars=120):
        prompt = normalize(message) or "merhaba"
        ids = [self.char_to_id.get(ch, 0) for ch in prompt]
        context = ([0] * CONTEXT_SIZE + ids)[-CONTEXT_SIZE:]
        output = []
        for _ in range(max_chars):
            probs = self.forward(context)
            probs = np.power(np.clip(probs, 1e-12, 1.0), 1 / 0.65)
            probs /= probs.sum()
            next_id = int(self.rng.choice(len(self.chars), p=probs))
            ch = self.id_to_char[next_id]
            output.append(ch)
            context = context[1:] + [next_id]
            if ch == "\n" and len(output) > 25:
                break
        return "".join(output).strip() or "Henuz cevap uretemedim."

def main():
    print("=" * 56)
    print("                  DATADEV AI")
    print("             CMD SOHBET PROTOTIPI")
    print("=" * 56)
    try:
        model = DataDevModel()
    except Exception as exc:
        print("Baslatma hatasi:", exc)
        input("Cikmak icin Enter...")
        return
    print("DataDev AI hazir. Mesajini yaz ve Enter'a bas.")
    print("Cikmak icin /cikis yaz. Temizlemek icin /temizle.")
    print("Not: Bu ilk model karakter uretir; her yanit anlamli olmayabilir.\n")
    while True:
        try:
            message = input("Sen > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDataDev AI kapatiliyor.")
            break
        if not message:
            continue
        command = message.lower()
        if command in ("/cikis", "/exit", "exit", "quit"):
            print("DataDev AI > Gorusuruz!")
            break
        if command == "/temizle":
            print("\n" * 35)
            continue
        try:
            print("DataDev AI > " + model.reply(message) + "\n")
        except Exception as exc:
            print("Yanıt hatasi:", exc)

if __name__ == "__main__":
    main()
