# -*- coding: utf-8 -*-
"""DataDev AI - yerel sohbet penceresi."""
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox
import json
import numpy as np
import unicodedata
import threading

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "datadev_ai_model.npz"
VOCAB_PATH = BASE / "datadev_ai_vocab.json"

CONTEXT_SIZE = 8
EMBED_SIZE = 16
HIDDEN_SIZE = 64

def normalize(text):
    text = text.lower()
    replacements = str.maketrans({
        "ı": "i", "İ": "i", "ş": "s", "ğ": "g",
        "ü": "u", "ö": "o", "ç": "c"
    })
    text = text.translate(replacements)
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))

class DataDevModel:
    def __init__(self):
        if not MODEL_PATH.exists() or not VOCAB_PATH.exists():
            raise FileNotFoundError("Model dosyalari bulunamadi. Once datadev_ai.py dosyasini calistir.")
        self.chars = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
        self.char_to_id = {ch: i for i, ch in enumerate(self.chars)}
        self.id_to_char = {i: ch for i, ch in enumerate(self.chars)}
        with np.load(MODEL_PATH) as data:
            self.E = data["E"]
            self.W1 = data["W1"]
            self.b1 = data["b1"]
            self.W2 = data["W2"]
            self.b2 = data["b2"]
        self.rng = np.random.default_rng()

    def forward(self, context):
        embedded = self.E[np.asarray([context], dtype=np.int64)]
        flat = embedded.reshape(1, -1)
        hidden = np.tanh(flat @ self.W1 + self.b1)
        logits = hidden @ self.W2 + self.b2
        logits -= np.max(logits, axis=1, keepdims=True)
        probs = np.exp(logits)
        return probs[0] / probs.sum()

    def reply(self, message, max_chars=120):
        prompt = normalize(message)
        if not prompt.strip():
            prompt = "merhaba"
        ids = [self.char_to_id.get(ch, 0) for ch in prompt]
        context = ([0] * CONTEXT_SIZE + ids)[-CONTEXT_SIZE:]
        output = []
        for _ in range(max_chars):
            probs = self.forward(context)
            # Temperature 0.65: biraz daha tutarli, yine de rastgele uretim.
            probs = np.power(np.clip(probs, 1e-12, 1.0), 1 / 0.65)
            probs /= probs.sum()
            next_id = int(self.rng.choice(len(self.chars), p=probs))
            ch = self.id_to_char[next_id]
            output.append(ch)
            context = context[1:] + [next_id]
            if ch == "\n" and len(output) > 25:
                break
        answer = "".join(output).strip()
        return answer or "Henuz anlamli bir cevap uretemedim."

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DataDev AI | Sohbet")
        self.root.geometry("820x620")
        self.root.minsize(600, 440)
        self.root.configure(bg="#111827")

        header = tk.Frame(root, bg="#172033", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="DataDev AI", bg="#172033", fg="#f9fafb",
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(header, text="Yerel prototip • Yanıtlar deneysel olabilir",
                 bg="#172033", fg="#aab7cf", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        self.chat = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, state="disabled", padx=14, pady=12,
            bg="#0b1220", fg="#e5e7eb", insertbackground="white",
            font=("Segoe UI", 11), relief="flat", borderwidth=0
        )
        self.chat.pack(fill="both", expand=True, padx=14, pady=14)
        self.chat.tag_config("you", foreground="#93c5fd", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("ai", foreground="#86efac", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("body", foreground="#e5e7eb")
        self.chat.tag_config("note", foreground="#9ca3af", font=("Segoe UI", 9))

        bottom = tk.Frame(root, bg="#111827", padx=14, pady=0)
        bottom.pack(fill="x")
        self.entry = tk.Entry(bottom, font=("Segoe UI", 12), bg="#1f2937",
                              fg="#f9fafb", insertbackground="white",
                              relief="flat", bd=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=12, padx=(0, 8))
        self.entry.bind("<Return>", self.send_event)
        self.send_button = tk.Button(bottom, text="Gönder", command=self.send,
                                     bg="#2563eb", fg="white", activebackground="#1d4ed8",
                                     activeforeground="white", relief="flat",
                                     padx=20, pady=10, font=("Segoe UI", 10, "bold"))
        self.send_button.pack(side="right")

        try:
            self.model = DataDevModel()
        except Exception as exc:
            messagebox.showerror("DataDev AI başlatılamadı", str(exc))
            root.after(100, root.destroy)
            return

        self.add_message("DataDev AI", "Merhaba! Ben DataDev AI'nin ilk sohbet prototipiyim. Bir şey yazıp deneyebilirsin.")
        self.add_message("Sistem", "Not: Bu küçük model yalnızca sınırlı eğitim örnekleri gördü; anlamsız yanıtlar verebilir.", "note")
        self.entry.focus_set()

    def add_message(self, who, text, tag=None):
        self.chat.configure(state="normal")
        if tag:
            self.chat.insert(tk.END, who + ": ", tag)
            self.chat.insert(tk.END, text + "\n\n", "note")
        else:
            label_tag = "you" if who == "Sen" else "ai"
            self.chat.insert(tk.END, who + ": ", label_tag)
            self.chat.insert(tk.END, text + "\n\n", "body")
        self.chat.configure(state="disabled")
        self.chat.see(tk.END)

    def send_event(self, event):
        self.send()
        return "break"

    def send(self):
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, tk.END)
        self.add_message("Sen", message)
        self.send_button.configure(state="disabled", text="...")
        self.entry.configure(state="disabled")
        threading.Thread(target=self.generate_reply, args=(message,), daemon=True).start()

    def generate_reply(self, message):
        try:
            answer = self.model.reply(message)
        except Exception as exc:
            answer = "Yanıt üretilirken hata oluştu: " + str(exc)
        self.root.after(0, self.finish_reply, answer)

    def finish_reply(self, answer):
        self.add_message("DataDev AI", answer)
        self.send_button.configure(state="normal", text="Gönder")
        self.entry.configure(state="normal")
        self.entry.focus_set()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    if hasattr(app, "model"):
        root.mainloop()
