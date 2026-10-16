from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
LOG = BASE / "datadev_gpt_v2_train.log"
SVG = BASE / "datadev_gpt_v2_loss_grafik.svg"
REPORT = BASE / "datadev_gpt_v2_loss_analizi.txt"

rows = []
for line in LOG.read_text(encoding="utf-8").splitlines():
    m = re.search(r"Adım\s+(\d+)/900\s+\|\s+eğitim loss ([0-9.]+)\s+\|\s+doğrulama loss ([0-9.]+)", line)
    if m:
        rows.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
if len(rows) < 2:
    raise SystemExit("Yeni eğitim kaydı bulunamadı.")

def smooth(values, n=5):
    return [sum(values[max(0,i-n+1):i+1])/len(values[max(0,i-n+1):i+1]) for i in range(len(values))]
steps = [r[0] for r in rows]
tr = [r[1] for r in rows]
va = [r[2] for r in rows]
tr_s, va_s = smooth(tr), smooth(va)
W,H,L,R,T,B = 1100,650,90,35,70,85
pw,ph = W-L-R,H-T-B
lo,hi = min(tr+va)-0.15,max(tr+va)+0.15
def xm(s): return L+(s-steps[0])/(steps[-1]-steps[0])*pw
def ym(v): return T+(hi-v)/(hi-lo)*ph
def path(vals):
    return " ".join(("M" if i==0 else "L")+f" {xm(steps[i]):.1f},{ym(v):.1f}" for i,v in enumerate(vals))
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
'<rect width="100%" height="100%" fill="white"/>',
'<text x="550" y="32" font-family="Arial" font-size="22" font-weight="bold" text-anchor="middle">DataDev GPT v2 — loss eğrisi</text>',
'<text x="550" y="53" font-family="Arial" font-size="12" text-anchor="middle">900 adım • ham ölçümler ve 5 ölçümlük hareketli ortalama</text>']
for j in range(6):
    v=lo+(hi-lo)*j/5; yy=ym(v)
    svg += [f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="#ddd"/>',
            f'<text x="{L-12}" y="{yy+4:.1f}" font-family="Arial" font-size="12" text-anchor="end">{v:.2f}</text>']
for s in [steps[0],150,300,450,600,750,steps[-1]]:
    xx=xm(s)
    svg += [f'<line x1="{xx:.1f}" y1="{T}" x2="{xx:.1f}" y2="{H-B}" stroke="#eee"/>',
            f'<text x="{xx:.1f}" y="{H-B+25}" font-family="Arial" font-size="12" text-anchor="middle">{s}</text>']
svg += [f'<path d="{path(tr)}" fill="none" stroke="#9bbde5" stroke-width="1.4"/>',
        f'<path d="{path(va)}" fill="none" stroke="#e8b08a" stroke-width="1.4"/>',
        f'<path d="{path(tr_s)}" fill="none" stroke="#2368b2" stroke-width="3"/>',
        f'<path d="{path(va_s)}" fill="none" stroke="#c45b19" stroke-width="3"/>',
        f'<text x="{L+10}" y="{T+20}" font-family="Arial" font-size="13" fill="#2368b2">Mavi: eğitim loss ortalaması</text>',
        f'<text x="{L+10}" y="{T+40}" font-family="Arial" font-size="13" fill="#c45b19">Turuncu: doğrulama loss ortalaması</text>',
        f'<text x="{W/2}" y="{H-25}" font-family="Arial" font-size="14" text-anchor="middle">Eğitim adımı</text>',
        f'<text x="22" y="{H/2}" font-family="Arial" font-size="14" text-anchor="middle" transform="rotate(-90 22 {H/2})">Loss (düşük daha iyi)</text>',
        '</svg>']
SVG.write_text("\n".join(svg), encoding="utf-8")

def avg(a): return sum(a)/len(a)
report = f"""DATADEV GPT v2 LOSS ANALİZİ

Ölçüm sayısı: {len(rows)}
Başlangıç eğitim/doğrulama loss: {tr[0]:.3f} / {va[0]:.3f}
Son eğitim/doğrulama loss: {tr[-1]:.3f} / {va[-1]:.3f}
İlk 5 ölçüm doğrulama ortalaması: {avg(va[:5]):.3f}
Son 5 ölçüm doğrulama ortalaması: {avg(va[-5:]):.3f}
En düşük doğrulama ölçümü: {min(va):.3f} (adım {steps[va.index(min(va))]})

Yorum: Genel eğilim aşağı; son doğrulama loss'u ilk değerden belirgin biçimde düşük.
Hareketli ortalama kısa dalgalanmaları azaltır. Loss düşmesi, modelin akıcı ve doğru
Türkçe ürettiğini tek başına kanıtlamaz. Bu yüzden sohbet modunda makale eşleştirmesi
güçlü olduğunda kaynaklı yanıt kullanılır; kaynak bulunamazsa deneysel model denenir.

Grafik: {SVG.name}
"""
REPORT.write_text(report, encoding="utf-8")
print(report)
print(f"Grafik oluşturuldu: {SVG}")
