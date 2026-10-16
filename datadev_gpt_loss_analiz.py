# -*- coding: utf-8 -*-
from pathlib import Path
import re, statistics

BASE = Path(__file__).resolve().parent
LOG = BASE / "datadev_gpt_train.log"
SVG = BASE / "datadev_gpt_loss_grafik.svg"
REPORT = BASE / "datadev_gpt_loss_analizi.txt"

rows = []
for line in LOG.read_text(encoding="utf-8").splitlines():
    m = re.search(r"Adım\s+(\d+)/1200\s+\|\s+eğitim loss ([0-9.]+)\s+\|\s+doğrulama loss ([0-9.]+)", line)
    if m:
        rows.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
# Keep latest complete training run and unique step values.
by_step = {r[0]: r for r in rows}
rows = [by_step[k] for k in sorted(by_step)]
if len(rows) < 5:
    raise SystemExit("1200 adımlık eğitim kayıtları bulunamadı.")

def moving_average(values, window=5):
    return [sum(values[max(0, i-window+1):i+1]) / len(values[max(0, i-window+1):i+1]) for i in range(len(values))]

steps = [r[0] for r in rows]
train = [r[1] for r in rows]
val = [r[2] for r in rows]
train_s = moving_average(train)
val_s = moving_average(val)

W, H = 1100, 650
L, R, T, B = 90, 35, 70, 85
plot_w, plot_h = W-L-R, H-T-B
ymin = max(0, min(train + val) - 0.2)
ymax = max(train + val) + 0.2
def xmap(s): return L + (s-min(steps))/(max(steps)-min(steps))*plot_w
def ymap(v): return T + (ymax-v)/(ymax-ymin)*plot_h
def path_for(vals):
    return " ".join(("M" if i == 0 else "L") + f" {xmap(steps[i]):.1f},{ymap(v):.1f}" for i,v in enumerate(vals))

parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
'<rect width="100%" height="100%" fill="#ffffff"/>',
'<text x="550" y="32" font-family="Arial" font-size="22" font-weight="bold" text-anchor="middle">DataDev GPT — eğitim loss eğrisi</text>',
'<text x="550" y="53" font-family="Arial" font-size="12" text-anchor="middle">Logdaki 1200 adımlık eğitim • ham ölçümler ve 5 ölçümlük hareketli ortalama</text>']
for j in range(6):
    v = ymin + (ymax-ymin)*j/5
    yy = ymap(v)
    parts.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="#dddddd"/>')
    parts.append(f'<text x="{L-12}" y="{yy+4:.1f}" font-family="Arial" font-size="12" text-anchor="end">{v:.2f}</text>')
for s in [1, 300, 600, 900, 1200]:
    xx=xmap(s)
    parts.append(f'<line x1="{xx:.1f}" y1="{T}" x2="{xx:.1f}" y2="{H-B}" stroke="#eeeeee"/>')
    parts.append(f'<text x="{xx:.1f}" y="{H-B+25}" font-family="Arial" font-size="12" text-anchor="middle">{s}</text>')
parts += [f'<path d="{path_for(train)}" fill="none" stroke="#9bbde5" stroke-width="1.5" opacity="0.8"/>',
          f'<path d="{path_for(val)}" fill="none" stroke="#e8b08a" stroke-width="1.5" opacity="0.8"/>',
          f'<path d="{path_for(train_s)}" fill="none" stroke="#2368b2" stroke-width="3"/>',
          f'<path d="{path_for(val_s)}" fill="none" stroke="#c45b19" stroke-width="3"/>',
          f'<text x="{L+10}" y="{T+20}" font-family="Arial" font-size="13" fill="#2368b2">Mavi: eğitim (5 ölçümlük ortalama)</text>',
          f'<text x="{L+10}" y="{T+40}" font-family="Arial" font-size="13" fill="#c45b19">Turuncu: doğrulama (5 ölçümlük ortalama)</text>',
          f'<text x="{W/2}" y="{H-25}" font-family="Arial" font-size="14" text-anchor="middle">Eğitim adımı</text>',
          f'<text x="22" y="{H/2}" font-family="Arial" font-size="14" text-anchor="middle" transform="rotate(-90 22 {H/2})">Loss (düşük olması daha iyi)</text>',
          '</svg>']
SVG.write_text("\n".join(parts), encoding="utf-8")

def avg(seq): return sum(seq)/len(seq)
first_train, last_train = avg(train[:4]), avg(train[-4:])
first_val, last_val = avg(val[:4]), avg(val[-4:])
best_val_row = min(rows, key=lambda r:r[2])
last10_val = avg(val[-10:])
prev10_val = avg(val[-20:-10]) if len(val) >= 20 else avg(val[:-10])
report = f"""DATADEV GPT LOSS ANALİZİ

Grafik: {SVG.name}
Ölçüm sayısı: {len(rows)} (her 30 adımda bir; her eğitim adımının kaydı değil)

Başlangıçtaki ilk 4 ölçüm ortalaması:
- Eğitim loss: {first_train:.3f}
- Doğrulama loss: {first_val:.3f}

Son 4 ölçüm ortalaması:
- Eğitim loss: {last_train:.3f}
- Doğrulama loss: {last_val:.3f}

Son 10 ölçüm doğrulama ortalaması: {last10_val:.3f}
Önceki 10 ölçüm doğrulama ortalaması: {prev10_val:.3f}
En düşük tek doğrulama ölçümü: {best_val_row[2]:.3f} (adım {best_val_row[0]})
Son kayıtta eğitim/doğrulama loss: {train[-1]:.3f} / {val[-1]:.3f}

YORUM:
- Genel yön aşağı: model eğitim sırasında örüntü öğrenmiş.
- Ölçümler dalgalı; son ölçüm tek başına düzlüğe ulaşıldığını veya geçildiğini kanıtlamaz.
- Doğrulama loss'unu tek ölçüm yerine hareketli ortalamayla izlemek daha anlamlı.
- Bu küçük karakter-seviyeli modelin loss'u düşse bile anlaşılır Türkçe üreteceği garanti değil.
- Mevcut log, 1200 adımdan sonra eğitim sürdürülürse ne olacağını göstermez; bunu öğrenmek için kontrollü devam eğitimi ve aynı doğrulama seti gerekir.
"""
REPORT.write_text(report, encoding="utf-8")
print(report)
print(f"Grafik kaydedildi: {SVG}")
