from pathlib import Path
p = Path.home() / "Desktop" / "ChatGPT" / "DataDevAI" / "datadev_gpt_v4.py"
s = p.read_text(encoding="utf-8")
old = 'LOG_FILE = BASE / "datadev_gpt_v4_train.log"\nGROQ_KEY_FILE = BASE / "groq_api_key.txt"'
new = 'LOG_FILE = BASE / "datadev_gpt_v4_train.log"\nINTERACTION_TRAINING_FILE = BASE / "datadev_interaction_training.jsonl"\nGROQ_KEY_FILE = BASE / "groq_api_key.txt"'
if old not in s:
    raise SystemExit("PATCH1 pattern missing")
s = s.replace(old, new, 1)
old2 = '    train_examples = list(examples)\n    val_examples = []\n    for path in article_paths:'
new2 = '''    train_examples = list(examples)
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
    val_examples = []
    for path in article_paths:'''
if old2 not in s:
    raise SystemExit("PATCH2 pattern missing")
s = s.replace(old2, new2, 1)
p.write_text(s, encoding="utf-8")
print("Updated local training corpus to include only manually approved examples.")
