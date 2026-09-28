"""Verify a browser-downloaded original PDF, copy it, and register collector state."""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macro_bulk_downloader import Report, State, is_pdf, safe_filename


def main():
    parser = argparse.ArgumentParser()
    for arg in ("house", "doc-id", "title", "published", "url", "file"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    source = Path(args.file).resolve(strict=True)
    raw = source.read_bytes()
    if not is_pdf(raw):
        raise SystemExit("Not a complete original PDF: " + str(source))
    base = Path(__file__).resolve().parents[1]
    target_dir = base / "outdated" / args.house
    report = Report(args.house, args.doc_id, args.title, args.published,
                    args.url, args.url, published=args.published)
    target = target_dir / safe_filename(args.title, args.doc_id, date.fromisoformat(args.published))
    target_dir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise SystemExit("Different existing file; refusing overwrite: " + str(target))
    else:
        with target.open("xb") as output:
            output.write(raw)
        shutil.copystat(source, target)
    if target.read_bytes() != raw:
        raise SystemExit("Copy verification failed: " + str(target))
    state = State(base / ".collector")
    state.record(report)
    state.result(report, "downloaded", path=target, raw=raw)
    state.export()
    state.db.close()
    print(json.dumps({"house": args.house, "doc_id": args.doc_id,
                      "path": str(target), "bytes": len(raw)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
