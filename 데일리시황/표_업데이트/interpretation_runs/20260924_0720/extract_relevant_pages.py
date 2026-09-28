from pathlib import Path
import fitz

root = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\outdated")
patterns = ("PMI", "Consumer sentiment", "inflation", "CPI")
for path in sorted(root.rglob("*.pdf")):
    if not path.name.startswith("20260923_") or not any(p.lower() in path.name.lower() for p in patterns):
        continue
    print(f"\n===== {path.parent.name} | {path.name} =====")
    doc = fitz.open(path)
    for index, page in enumerate(doc):
        text = page.get_text("text").strip()
        print(f"\n--- PAGE {index + 1} ---\n{text}")
