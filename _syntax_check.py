import ast
from pathlib import Path
base=Path.home()/"Desktop"/"ChatGPT"/"DataDevAI"
for name in ("datadev_api.py","datadev_gpt_v4.py"):
    ast.parse((base/name).read_text(encoding="utf-8"), filename=name)
    print(name + ": syntax OK")
