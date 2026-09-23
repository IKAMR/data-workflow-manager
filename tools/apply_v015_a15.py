
from __future__ import annotations

import json
from pathlib import Path

OLD_VERSION = "2.13.0"
NEW_VERSION = "2.13.1"
OLD_COMMIT = "40a32ee0ae84ddf44d1f3c35f1860567ca262733"
NEW_COMMIT = "b27136ede491d3ec8b9e0ec9973ba455a0febbdf"
RUNTIME_AFFECTED = ["N5.28", "N5.30", "N5.32", "N5.33", "N5.64"]
INSPECTED_NOT_AFFECTED = ["N5.29", "N5.34"]

ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


def save_json(rel: str, value):
    path = ROOT / rel
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def add_unique(values: list, item):
    if item not in values:
        values.append(item)


def update_catalog():
    rel = "config/noark5/external/arkade5_test_catalog.json"
    data = load_json(rel)
    data["catalog_id"] = "arkade5-noark5-tests-v2.13.1"
    data["arkade_version"] = NEW_VERSION
    source = data.setdefault("source", {})
    source["commit"] = NEW_COMMIT
    source["commit_message"] = (
        "Merge pull request #194 from nasjonalarkivet/release/v2.13.1 - "
        "Fixes document directory detection and SIARD validation feedback"
    )
    source["verification_date"] = "2026-09-23"

    for row in data.get("tests") or []:
        provenance = row.get("source_provenance") or {}
        if provenance.get("commit") == OLD_COMMIT:
            provenance["commit"] = NEW_COMMIT
            row["source_provenance"] = provenance

    data["release_delta"] = {
        "from_version": OLD_VERSION,
        "to_version": NEW_VERSION,
        "base_commit": OLD_COMMIT,
        "release_commit": NEW_COMMIT,
        "noark5_test_implementations_changed": 0,
        "runtime_affected_test_ids": RUNTIME_AFFECTED,
        "inspected_not_runtime_affected_test_ids": INSPECTED_NOT_AFFECTED,
        "issue": "ARKADE-826",
        "scope": "TAR/DIAS document directory detection and relative path handling",
        "note_nb": (
            "De 54 Noark 5-testimplementasjonene er uendret. Endret "
            "dokumentfilinfrastruktur kan gi annet runtime-resultat for de fem "
            "oppførte testene ved TAR/DIAS-input."
        ),
    }
    save_json(rel, data)


def update_mapping():
    rel = "config/noark5/external/dwm_arkade5_mapping.json"
    data = load_json(rel)
    data["mapping_id"] = "dwm-arkade5-noark5-v2.13.1"
    data["dwm_version"] = "0.1.5-a15"
    data["arkade_version"] = NEW_VERSION
    data["arkade_source_commit"] = NEW_COMMIT
    data["release_delta"] = {
        "from_version": OLD_VERSION,
        "to_version": NEW_VERSION,
        "mapping_relations_changed": False,
        "note_nb": (
            "Relasjonene 1 equivalent / 21 partial / 19 complementary / "
            "13 arkade_only er uendret fra v2.13.0."
        ),
    }
    save_json(rel, data)


def update_policy():
    rel = "config/noark5/external/arkade5_coverage_policy.json"
    data = load_json(rel)
    data["arkade_version"] = NEW_VERSION
    data.setdefault("basis", {})["arkade_source_commit"] = NEW_COMMIT
    for row in data.get("documented_dwm_gaps") or []:
        reason = str(row.get("reason_nb") or "")
        row["reason_nb"] = reason.replace(
            "Arkade 5 v2.13.0", "Arkade 5 v2.13.1"
        )
    data["release_delta"] = {
        "from_version": OLD_VERSION,
        "to_version": NEW_VERSION,
        "coverage_policy_changed": False,
        "runtime_affected_gap_ids": [
            test_id for test_id in RUNTIME_AFFECTED
            if test_id in {"N5.28", "N5.30", "N5.32", "N5.33", "N5.64"}
        ],
    }
    save_json(rel, data)


def update_contract():
    rel = "config/noark5/external/arkade5_integration_contract.json"
    data = load_json(rel)
    data["contract_id"] = "dwm-arkade5-v2.13.1-integration-contract-v1"
    data["arkade_version"] = NEW_VERSION
    data["arkade_source_commit"] = NEW_COMMIT
    expected = data.setdefault("expected", {})
    expected["runtime_affected_test_count_v2_13_1"] = 5
    required = data.setdefault("required_files", [])
    add_unique(
        required,
        "config/noark5/external/arkade5_release_delta_2_13_1.json",
    )
    add_unique(required, "docs/ARKADE5-V2.13.1-CHANGE-IMPACT.md")
    data["version_delta"] = {
        "from_version": OLD_VERSION,
        "to_version": NEW_VERSION,
        "test_implementations_changed": 0,
        "runtime_affected_test_ids": RUNTIME_AFFECTED,
    }
    save_json(rel, data)


def update_profile():
    rel = "config/noark5/profile.json"
    data = load_json(rel)
    data.setdefault("capabilities", {})[
        "arkade_release_delta_tracking"
    ] = True
    mappings = data.setdefault("definitions", {}).setdefault(
        "external_mappings", []
    )
    add_unique(
        mappings,
        "config/noark5/external/arkade5_release_delta_2_13_1.json",
    )
    docs = data.setdefault("documentation", [])
    add_unique(docs, "docs/ARKADE5-V2.13.1-CHANGE-IMPACT.md")
    save_json(rel, data)


def update_docs():
    replacements = [
        "docs/ARKADE5-INTEGRATION-CONTRACT.md",
        "docs/ARKADE5-PRACTICAL-ACCEPTANCE.md",
        "docs/ARKADE5-RELEASE-READINESS.md",
    ]
    for rel in replacements:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "40a32ee0ae84ddf44d1f3c35f1860567ca262733",
            NEW_COMMIT,
        )
        text = text.replace("v2.13.0", "v2.13.1")
        text = text.replace("2.13.0", "2.13.1")
        path.write_text(text, encoding="utf-8")

    marker = "## Arkade 5 v2.13.1"
    appendix = """
## Arkade 5 v2.13.1

Katalogen er verifisert mot Arkade 5 v2.13.1, releasecommit
`b27136ede491d3ec8b9e0ec9973ba455a0febbdf`.

De 54 Noark 5-testimplementasjonene er uendret fra v2.13.0.
ARKADE-826 kan likevel endre runtime-resultat ved TAR/DIAS-input for
N5.28, N5.30, N5.32, N5.33 og N5.64. Se
`ARKADE5-V2.13.1-CHANGE-IMPACT.md`.
"""
    for rel in [
        "docs/ARKADE5-NOARK5-TESTS.md",
        "docs/ARKADE5-DWM-MAPPING.md",
    ]:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            text = text.rstrip() + "\n\n" + appendix.strip() + "\n"
            path.write_text(text, encoding="utf-8")


def main():
    update_catalog()
    update_mapping()
    update_policy()
    update_contract()
    update_profile()
    update_docs()
    print("v0.1.5-a15 Arkade 5 v2.13.1-oppdatering er brukt.")
    print("Kjør test.bat.")


if __name__ == "__main__":
    main()
