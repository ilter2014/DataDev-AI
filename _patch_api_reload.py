from pathlib import Path
p=Path.home()/"Desktop"/"ChatGPT"/"DataDevAI"/"datadev_api.py"
s=p.read_text(encoding="utf-8")
s=s.replace("_STOI = None\n_RATE_LOCK", "_STOI = None\n_MODEL_MTIME = None\n_RATE_LOCK", 1)
start=s.index("def load_local_model():")
end=s.index("\ndef make_local_draft",start)
new=r'''def load_local_model():
    """Load or reload the local checkpoint when its file timestamp changes."""
    global _MODEL, _CHARS, _STOI, _MODEL_MTIME
    with MODEL_LOCK:
        candidates = [
            BASE / "datadev_gpt_v4_model.pt",
            BASE / "datadev_gpt_v3_model.pt",
        ]
        checkpoint = next((p for p in candidates if p.exists()), None)
        if checkpoint is None:
            raise FileNotFoundError("Model dosyasi bulunamadi. Once model egitimini tamamlayin.")
        checkpoint_mtime = checkpoint.stat().st_mtime
        if _MODEL is not None and _MODEL_MTIME == checkpoint_mtime:
            return _MODEL, _CHARS, _STOI
        saved = torch.load(checkpoint, map_location=core.DEVICE, weights_only=False)
        chars = saved.get("chars")
        state = saved.get("model")
        if not isinstance(chars, list) or not state:
            raise RuntimeError("Model checkpoint formati beklenenden farkli.")
        model = core.TinyGPT(len(chars)).to(core.DEVICE)
        model.load_state_dict(state)
        model.eval()
        _MODEL, _CHARS, _STOI = model, chars, {ch: i for i, ch in enumerate(chars)}
        _MODEL_MTIME = checkpoint_mtime
        print("[DataDev API] Local model loaded/reloaded from " + checkpoint.name, flush=True)
        return _MODEL, _CHARS, _STOI
'''
s=s[:start]+new+s[end:]
p.write_text(s,encoding="utf-8")
print("API will reload the local model after a new checkpoint is saved.")
