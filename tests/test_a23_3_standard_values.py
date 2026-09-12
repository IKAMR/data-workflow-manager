import json
from pathlib import Path

ROOT=Path(__file__).parents[1]

def _load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))

def test_a23_3_version():
    ns={}
    exec((ROOT/"version.py").read_text(encoding="utf-8"),ns)
    assert ns["VERSION"]=="0.1.2-a23"

def test_new_sets_are_v5_only_and_external():
    reg=_load("config/noark5/standards/noark5_standard_values.json")
    ids={"M087_korrespondanseparttype","M089_slettingstype","M450_kassasjonsvedtak","M500_tilgangsrestriksjon","M502_skjermingMetadata","M503_skjermingDokument","M506_gradering","M508_elektroniskSignaturVerifisert","M056_presedensstatus"}
    assert ids <= set(reg["versions"]["5.0"]["value_sets"])
    for v in ("3.1","4.0"):
        assert not (ids & set(reg["versions"][v]["value_sets"]))

def test_catalog_checks_reference_registry():
    reg=_load("config/noark5/standards/noark5_standard_values.json")
    cat=_load("config/noark5/tests/xpath_catalog_2026_05_26.json")
    v5=set(reg["versions"]["5.0"]["value_sets"])
    for test in cat["tests"]:
        for check in test.get("standard_value_checks",[]):
            if "5.0" in check.get("versions",[]):
                assert check["value_set_id"] in v5

def test_no_new_noark_values_hardcoded_in_engine():
    engine=(ROOT/"noark5_workflow/analysis/xpath_test_engine.py").read_text(encoding="utf-8")
    for value in ("Kopimottaker","Sletting av produksjonsformat","Vurderes senere","Unntatt offentlighet","Strengt hemmelig (sikkerhetsgrad)"):
        assert value not in engine
