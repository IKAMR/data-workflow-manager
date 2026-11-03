"""Read-only smoke check of the v0.1.8-a1 GUI-independent DWM API.

Usage: py tools/dwm_api_smoke.py PATH_TO_JOBLIST.n5jobs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application_api import DwmApplication


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vis jobber og lagringsstier uten GUI eller kjøring")
    parser.add_argument("job_list", type=Path)
    args = parser.parse_args(argv)
    try:
        app = DwmApplication()
        snapshot = app.open_job_list(args.job_list)
        errors = app.check_storage()
    except Exception as exc:
        print(f"FEIL: {exc}", file=sys.stderr)
        return 2
    result = snapshot.as_dict()
    result["storage_warnings"] = list(errors)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
