import importlib.util,tempfile,json
from pathlib import Path
p=Path(__file__).resolve().parents[1] / 'tools' / 'noark5_batch_overview_a6.py'
spec=importlib.util.spec_from_file_location('a7',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    for label, job, run in [('1502_029','JOB-001','a01'),('1502_030','JOB-002','a01'),('1502_031','JOB-001','a02'),('1502_032','JOB-004',None)]:
        path=base/label/'repository_operations'/'dwm'
        if run:path/=run
        path=path/'noark5_reports'/'depot_validation'/f'{job}__RUN-20261004-041533-6f71b7fc'
        path.mkdir(parents=True)
        (path/'depot_validation_report.json').write_text(json.dumps({'report_type':'noark5_depot_validation','archive_parts':[],'summary':{'archive_part_count':1}}))
        (base/label/'content'/'DOKUMENT').mkdir(parents=True)
        (base/label/'content'/'DOKUMENT'/'depot_validation_report.json').write_text('DECOY')
    files=m.locate_reports(base)
    assert len(files)==4,files
    items=m.choose_latest_per_job([m.extract(f) for f in files]);assert len(items)==4
    assert len([x for x in items if x['job']=='JOB-001'])==2
    assert all(x['go_assessment']['status'] in ('STOPP','AVKLARING') for x in items)
    assert not any('content' in str(p) for p in files)
    print('OK: 4 rapporter, dwm/a01, dwm/a02 og dwm direkte; JOB-ID-kollisjon bevart; dokumentsok utelatt; forsiktig GO')
