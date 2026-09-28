import json
from pathlib import Path
import sys

import pypdfium2 as pdfium
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "output" / "latest_outputs.json"


def default_pdf():
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Run build_market_10d_outputs.py first: {MANIFEST}")
    return Path(json.loads(MANIFEST.read_text(encoding="utf-8"))["pdf"])


PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else default_pdf()
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else PDF.parent
OUT.mkdir(parents=True, exist_ok=True)

pdf = pdfium.PdfDocument(str(PDF))
thumbs = []
for index in range(len(pdf)):
    image = pdf[index].render(scale=1.2).to_pil().convert("RGB")
    image.save(OUT / f"page-{index + 1:02d}.png")
    thumb = image.copy()
    thumb.thumbnail((420, 300))
    card = Image.new("RGB", (440, 335), "white")
    card.paste(thumb, ((440 - thumb.width) // 2, 10))
    ImageDraw.Draw(card).text((12, 312), f"p.{index + 1}", fill="#102A43")
    thumbs.append(card)

cols = 2
per_sheet = 8
for sheet_index, start in enumerate(range(0, len(thumbs), per_sheet), 1):
    batch = thumbs[start:start + per_sheet]
    rows = (len(batch) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 440, rows * 335), "#DCE3EC")
    for idx, thumb in enumerate(batch):
        sheet.paste(thumb, ((idx % cols) * 440, (idx // cols) * 335))
    sheet.save(OUT / f"contact-sheet-{sheet_index:02d}.png")

print(f"pages={len(pdf)}")
print(OUT)
