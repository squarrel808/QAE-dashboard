# run_all.py — fetch → build 한 번에 실행
import sys

import fetch_macrographs
import build_graphs

if __name__ == "__main__":
    rc = fetch_macrographs.main()
    if rc != 0:
        sys.exit(rc)
    sys.exit(build_graphs.main())
