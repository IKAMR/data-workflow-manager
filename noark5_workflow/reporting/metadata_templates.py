"""Reusable operator templates, stored separately from immutable source evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def template_path() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / "DataWorkflowManager" / "metadata_templates.json"


def load_templates() -> list[dict]:
    path = template_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [{"kind": "template", "name": str(x.get("name", "")), "fields": x["fields"]}
            for x in data if isinstance(x, dict) and isinstance(x.get("fields"), dict) and x.get("name")]


def save_template(name: str, fields: dict[str, str]) -> Path:
    name = name.strip()
    if not name or len(name) > 120:
        raise ValueError("Malnavn må være mellom 1 og 120 tegn.")
    templates = load_templates()
    if any(x["name"].casefold() == name.casefold() for x in templates):
        raise ValueError("En mal med dette navnet finnes allerede.")
    templates.append({"kind": "template", "name": name,
                      "fields": {str(k): str(v) for k, v in fields.items() if v}})
    path = template_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".templates-", suffix=".tmp", delete=False) as tmp:
            temp_name = tmp.name
            json.dump(templates, tmp, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return path
