from __future__ import annotations
import html, json, re
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

def safe_component(value: str, fallback: str = "report") -> str:
    value = _SAFE_NAME.sub("_", str(value or "").strip()).strip("._")
    return value or fallback

def ensure_output_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target

def write_json_report(payload: dict[str, Any], *, output_dir: str | Path, basename: str) -> Path:
    target = ensure_output_dir(output_dir) / f"{safe_component(basename)}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target

def html_document(*, title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2rem; color: #1e1e1e; }}
h1, h2, h3 {{ margin-bottom: .4rem; }}
.meta {{ color: #555; margin-bottom: 1.2rem; }}
.summary {{ padding: .8rem 1rem; background: #f2f4f7; border-radius: .4rem; margin-bottom: 1.2rem; }}
.card {{ border: 1px solid #d7dce2; border-radius: .4rem; padding: 1rem; margin: .8rem 0; page-break-inside: avoid; }}
.error {{ border-left: .45rem solid #b91c1c; }}
.warning {{ border-left: .45rem solid #b7791f; }}
.review {{ border-left: .45rem solid #5b5bd6; }}
.ok {{ border-left: .45rem solid #2f855a; }}
.small {{ color: #555; font-size: .92rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #ddd; text-align: left; padding: .4rem; vertical-align: top; }}
@media print {{ body {{ margin: 1cm; }} }}
</style>
</head>
<body>
{body}
</body>
</html>"""

def write_html_report(html_text: str, *, output_dir: str | Path, basename: str) -> Path:
    target = ensure_output_dir(output_dir) / f"{safe_component(basename)}.html"
    target.write_text(html_text, encoding="utf-8")
    return target
