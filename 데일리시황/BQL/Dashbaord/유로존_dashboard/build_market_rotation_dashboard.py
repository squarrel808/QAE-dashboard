"""Build the global equity dashboard and refresh its local Macro Hub copy.

Calculations and Stock Map rendering remain in the shared builder/template.
Custom output/asset/template/region options leave the live embed alone unless
an explicit --sync-embed path is given. No Git or hosting operations run here.
"""

import argparse
from pathlib import Path
import subprocess
import sys


def build_command(arguments: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--no-sync-embed", action="store_true")
    options, forwarded = parser.parse_known_args(arguments)
    flags = {argument.split("=", 1)[0] for argument in forwarded if argument.startswith("--")}
    if options.no_sync_embed and "--sync-embed" in flags:
        parser.error("Use either --no-sync-embed or --sync-embed, not both")
    builder = Path(__file__).resolve().parent.parent / "build_regional_dashboards.py"
    custom_build = bool(flags & {"--asset-root", "--output-root", "--europe-template", "--region"})
    wants_help = bool(flags & {"--help"}) or "-h" in forwarded
    if not options.no_sync_embed and not custom_build and "--sync-embed" not in flags and not wants_help:
        qae_root = builder.parents[3]
        forwarded.extend(["--sync-embed", str(qae_root / "macro_hub" / "public" / "embeds" / "market_rotation.html")])
    return [sys.executable, "-X", "utf8", str(builder), "--region", "europe", *forwarded]


if __name__ == "__main__":
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print("Default: rebuild from Master and synchronize the local Market Rotation embed.\n"
              "--no-sync-embed: generate dashboard HTML only. Other options below go to the shared builder.", flush=True)
    raise SystemExit(subprocess.call(build_command(sys.argv[1:])))
