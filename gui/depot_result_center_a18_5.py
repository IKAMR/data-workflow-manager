from __future__ import annotations

import re
from pathlib import Path

from .depot_result_center_a18_4 import DepotResultCenterDialogA18_4


_JOB_RE = re.compile(r"(JOB-\d+)", re.IGNORECASE)


def _context_from_report(model: dict, report_path: str | Path | None) -> tuple[str, str, int]:
    """Return (label, job_id, archive_part_count) without re-analysing source data."""
    summary = model.get("summary") or {}
    archive_count = int(summary.get("archive_part_count") or len(model.get("archive_parts") or []))

    candidates: list[str] = []
    evidence = model.get("evidence") or {}
    for key in ("source_xpath_run", "source_presentation_file"):
        value = evidence.get(key)
        if value:
            candidates.append(str(value))
    if report_path:
        candidates.append(str(report_path))

    job_id = ""
    label = ""

    # JOB-xxx normally appears in the generated artifact path.
    for value in candidates:
        match = _JOB_RE.search(value)
        if match:
            job_id = match.group(1).upper()
            break

    # Prefer the Noark 5 extraction root: the directory immediately above
    # repository_operations in any materialized source path.
    for value in candidates:
        try:
            parts = Path(value).parts
        except Exception:
            continue
        lower = [p.casefold() for p in parts]
        if "repository_operations" in lower:
            idx = lower.index("repository_operations")
            if idx > 0:
                label = parts[idx - 1]
                break

    # Fallback to an explicit label if a later report model provides one.
    if not label:
        for container in (model, evidence, model.get("source") or {}):
            for key in ("label", "LABEL", "extraction_label", "delivery_label"):
                value = container.get(key) if isinstance(container, dict) else None
                if value:
                    label = str(value).strip()
                    break
            if label:
                break

    return label or "Ukjent uttrekk", job_id or "Ukjent jobb", archive_count


class DepotResultCenterDialogA18_5(DepotResultCenterDialogA18_4):
    """a18.5: keep extraction/job context visible in every depot result view."""

    def __init__(self, master, **kwargs):
        model = kwargs.get("model") or {}
        report_path = kwargs.get("report_path")
        super().__init__(master, **kwargs)

        label, job_id, archive_parts = _context_from_report(model, report_path)
        self._a185_label = label
        self._a185_job_id = job_id
        self._a185_archive_parts = archive_parts

        # Context in the native window frame / task switcher.
        self.title(f"Resultatvisninger – Noark 5 – {label}")

        # Reuse the existing explanatory header rather than adding vertical bulk.
        context_text = (
            f"Uttrekk: {label}   |   Jobb: {job_id}   |   Arkivdeler: {archive_parts}\n"
            "Visningene leser den allerede genererte depotrapporten og kjører ingen ny analyse."
        )
        self._a185_replace_intro(context_text)

    def _a185_replace_intro(self, text: str) -> None:
        """Find the inherited intro label and turn it into a two-line context header."""
        for child in self.winfo_children():
            try:
                current = str(child.cget("text") or "")
            except Exception:
                continue
            if current.startswith("Visningene leser den allerede genererte depotrapporten"):
                try:
                    child.configure(text=text, justify="left", anchor="w")
                except Exception:
                    pass
                return
