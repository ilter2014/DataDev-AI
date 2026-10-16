# -*- coding: utf-8 -*-
"""Build a reproducible SVG loss chart and Markdown report from the v5 training log."""
from pathlib import Path
import re
import torch
import datadev_gpt_v5 as core

BASE = Path(__file__).resolve().parent
LOG = BASE / "datadev_gpt_v5_train.log"
MODEL = BASE / "datadev_gpt_v5_model.pt"
SVG = BASE / "datadev_gpt_v5_loss_grafik.svg"
REPORT = BASE / "DATADEV_GPT_V5_TRAINING_REPORT.md"
PATTERN = re.compile(r"Adım\s+(\d+)/(\d+).*?eğitim loss ([0-9.]+).*?doğrulama loss ([0-9.]+).*?en iyi ([0-9.]+) \(adım (\d+)\).*?\|\s+([0-9.]+) sn")

def main():
    if not LOG.exists() or not MODEL.exists():
        raise SystemExit("Eğitim logu veya v5 checkpoint bulunamadı.")
    rows = []
    for line in LOG.read_text(encoding="utf-8-sig").splitlines():
        match = PATTERN.search(line)
        if match:
            step, total, train, val, best, best_step, seconds = match.groups()
            rows.append({"step": int(step), "total": int(total), "train": float(train),
                         "val": float(val), "best": float(best), "best_step": int(best_step),
                         "seconds": float(seconds)})
    if not rows:
        raise SystemExit("Log içinde grafik oluşturulabilecek eğitim adımı bulunamadı.")
    checkpoint = torch.load(MODEL, map_location="cpu", weights_only=False)
    model = core.TinyGPT(len(checkpoint["chars"]))
    params = sum(p.numel() for p in model.parameters())
    cfg = checkpoint.get("config", {})
    first, last = rows[0], rows[-1]
    best_row = min(rows, key=lambda row: row["val"])
    width, height = 1000, 560
    left, right, top, bottom = 90, 35, 70, 85
    plot_w, plot_h = width - left - right, height - top - bottom
    y_values = [r["train"] for r in rows] + [r["val"] for r in rows]
    y_min = max(0.0, min(y_values) - 0.15)
    y_max = max(y_values) + 0.15
    x_max = max(r["step"] for r in rows)
    def x(step):
        return left + (step / x_max) * plot_w
    def y(value):
        return top + (y_max - value) / (y_max - y_min) * plot_h
    grid = []
    tick = round(y_min * 2) / 2
    while tick <= y_max + 0.001:
        yy = y(tick)
        grid.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" stroke="#30333D" stroke-width="1"/>')
        grid.append(f'<text x="{left-15}" y="{yy+5:.1f}" fill="#C9CDD6" font-size="14" text-anchor="end">{tick:.1f}</text>')
        tick += 0.5
    x_ticks = sorted(set([0, x_max//4, x_max//2, (3*x_max)//4, x_max]))
    for step in x_ticks:
        xx = x(step)
        grid.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{height-bottom}" stroke="#252832" stroke-width="1"/>')
        grid.append(f'<text x="{xx:.1f}" y="{height-bottom+27}" fill="#C9CDD6" font-size="14" text-anchor="middle">{step}</text>')
    train_points = " ".join(f"{x(r['step']):.1f},{y(r['train']):.1f}" for r in rows)
    val_points = " ".join(f"{x(r['step']):.1f},{y(r['val']):.1f}" for r in rows)
    best_x, best_y = x(best_row["step"]), y(best_row["val"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#0D0E13"/>
<text x="{left}" y="32" fill="#F4F6FA" font-size="23" font-weight="700">DataDev GPT v5 — Training Loss</text>
<text x="{left}" y="52" fill="#9CA3AF" font-size="13">{params:,} parameters · {len(checkpoint["chars"])}-character vocabulary · {last["total"]} steps</text>
{"".join(grid)}
<polyline points="{train_points}" fill="none" stroke="#5DD9C1" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<polyline points="{val_points}" fill="none" stroke="#E8EDF5" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<circle cx="{best_x:.1f}" cy="{best_y:.1f}" r="5" fill="#5DD9C1" stroke="#0D0E13" stroke-width="2"/>
<text x="{min(best_x+12,width-right-210):.1f}" y="{max(top+15,best_y-12):.1f}" fill="#5DD9C1" font-size="14">Best val {best_row["val"]:.3f} @ {best_row["step"]}</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#8B909B"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#8B909B"/>
<text x="{width/2}" y="{height-22}" fill="#D6DAE3" font-size="16" text-anchor="middle">Training step</text>
<text transform="translate(25 {height/2}) rotate(-90)" fill="#D6DAE3" font-size="16" text-anchor="middle">Cross-entropy loss (lower is better)</text>
<line x1="{width-270}" y1="36" x2="{width-240}" y2="36" stroke="#5DD9C1" stroke-width="3"/>
<text x="{width-232}" y="41" fill="#E8EDF5" font-size="14">Train</text>
<line x1="{width-165}" y1="36" x2="{width-135}" y2="36" stroke="#E8EDF5" stroke-width="3"/>
<text x="{width-127}" y="41" fill="#E8EDF5" font-size="14">Validation</text>
</svg>'''
    SVG.write_text(svg, encoding="utf-8")
    report = f"""# DataDev GPT v5 — Training Report

- **Parameters:** {params:,}
- **Architecture:** embedding {core.N_EMBD}, {core.N_HEAD} attention heads, {core.N_LAYER} transformer layers, context {core.BLOCK_SIZE}
- **Vocabulary:** {len(checkpoint['chars'])} characters
- **Training steps completed:** {last['step']:,} / {last['total']:,}
- **Best checkpoint step:** {best_row['step']:,}
- **Initial validation loss:** {first['val']:.4f}
- **Best validation loss:** {best_row['val']:.4f}
- **Final logged validation loss:** {last['val']:.4f}
- **Final logged training loss:** {last['train']:.4f}
- **Logged elapsed time:** {last['seconds']:.1f} seconds
- **Checkpoint config best validation loss:** {cfg.get('best_val', 'not recorded')}

![DataDev GPT v5 training loss](datadev_gpt_v5_loss_grafik.svg)

Validation loss measures next-character prediction on held-out text; lower is better. It does **not** by itself prove factual accuracy, reasoning quality, or conversational usefulness. The current model is a small character-level prototype.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"Created {SVG.name} and {REPORT.name}")
    print(f"Parameters: {params:,}; best validation loss: {best_row['val']:.4f} at step {best_row['step']}; final step: {last['step']}/{last['total']}")

if __name__ == "__main__":
    main()
