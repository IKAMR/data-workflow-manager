import json
from pathlib import Path
from noark5_workflow.analysis.xpath_test_engine import _standard_value_checks

ROOT=Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/'config/noark5/standards/noark5_standard_values.json').read_text(encoding='utf-8'))

def test_journalstatus_version_difference():
    assert len(REG['versions']['3.1']['value_sets']['M053_journalstatus']['values']) == 6
    assert len(REG['versions']['4.0']['value_sets']['M053_journalstatus']['values']) == 6
    assert len(REG['versions']['5.0']['value_sets']['M053_journalstatus']['values']) == 4

def test_generic_standard_comparison_keeps_additional_values():
    values={'status_counts':{'Arkivert':4,'Leverandoerverdi':2}}
    checks=[{'id':'journal_status','metric_id':'status_counts','value_set_id':'M053_journalstatus','versions':['5.0']}]
    result=_standard_value_checks(values,checks,REG)['journal_status']['versions']['5.0']
    assert result['status']=='additional_observed_values'
    assert result['additional_observed_values']=={'Leverandoerverdi':2}
    assert result['standard_value_counts']['Arkivert']==4
    assert result['observed_value_count']==6
    assert result['standard_observed_count']==4
    assert result['additional_observed_count']==2

def test_catalog_references_external_registry():
    cat=json.loads((ROOT/'config/noark5/tests/xpath_catalog_2026_05_26.json').read_text(encoding='utf-8'))
    assert cat['standard_values_registry']=='../standards/noark5_standard_values.json'
    assert all('standard_value_checks' in next(t for t in cat['tests'] if t['test_id']==tid) for tid in ['kdrs.c01','kdrs.c02','kdrs.c13','kdrs.c15','kdrs.c21','kdrs.c23','kdrs.c24'])


def test_run_test_adds_standard_layer_without_replacing_observed(tmp_path):
    cat=json.loads((ROOT/'config/noark5/tests/xpath_catalog_2026_05_26.json').read_text(encoding='utf-8'))
    test=next(t for t in cat['tests'] if t['test_id']=='kdrs.c15')
    xml = '<arkiv><registrering type="journalpost"><journalposttype>Inngående dokument</journalposttype><journalstatus>Godkjent av leder</journalstatus></registrering></arkiv>'
    (tmp_path/'arkivstruktur.xml').write_text(xml,encoding='utf-8')
    from noark5_workflow.analysis.xpath_test_engine import run_test
    result=run_test(test,tmp_path,standard_registry=REG)
    assert result['values']['journal_status_counts']=={'Godkjent av leder':1}
    std=result['values']['_standard_values']['journal_status']['versions']
    assert std['4.0']['status']=='all_observed_values_standard'
    assert std['5.0']['status']=='additional_observed_values'
    assert std['5.0']['additional_observed_values']=={'Godkjent av leder':1}


def test_no_observed_values_status():
    """Tom observert fordeling skal ikke rapporteres som standardverdisamsvar."""
    values = {"status_counts": {}}
    checks = [{"id": "journal_status", "metric_id": "status_counts", "value_set_id": "M053_journalstatus", "versions": ["5.0"]}]
    result = _standard_value_checks(values, checks, REG)["journal_status"]["versions"]["5.0"]
    assert result["status"] == "no_observed_values"
    assert result["observed_value_count"] == 0
    assert result["standard_observed_count"] == 0
    assert result["additional_observed_count"] == 0
