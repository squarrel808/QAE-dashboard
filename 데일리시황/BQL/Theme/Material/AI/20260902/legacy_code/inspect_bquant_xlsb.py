from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import numpy as np
import sys

builder_path = Path(r"C:\Users\USER\Downloads\유로존\dashbaord\build_market_rotation_dashboard.py")
spec = spec_from_file_location("bquant_builder", builder_path)
mod = module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

paths = [Path(p) for p in sys.argv[1:]]
out = []
for path in paths:
    rows = []
    for raw in mod.iter_raw_indices(path):
        metric_stats = {}
        for key, arr in raw.metrics.items():
            finite = np.isfinite(arr)
            metric_stats[key] = {
                "shape": list(arr.shape),
                "finite": int(finite.sum()),
                "last_date_finite": str(max((raw.dates[j] for j in range(len(raw.dates)) if finite[:, j].any()), default="")),
            }
        rows.append({
            "code": raw.code,
            "name": raw.name,
            "sheet": raw.sheet,
            "members": len(raw.tickers),
            "dates": len(raw.dates),
            "start": str(min(raw.dates)) if raw.dates else None,
            "end": str(max(raw.dates)) if raw.dates else None,
            "metrics": metric_stats,
        })
    out.append({"path": str(path), "size": path.stat().st_size, "indices": rows})

print(json.dumps(out, ensure_ascii=False, indent=2))
