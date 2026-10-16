from pathlib import Path
p=Path.home()/"Desktop"/"ChatGPT"/"DataDevAI"/"DataDev AI Groq Paneli.ps1"
s=p.read_text(encoding="utf-8")
s=s.replace("It becomes training material only after option 6 runs successfully.","It becomes training material only after option 5 runs successfully.")
p.write_text(s,encoding="utf-8")
print("Fixed training menu reference.")
