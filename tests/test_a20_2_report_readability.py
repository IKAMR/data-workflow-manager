"""Readability regressions a20.2: no change to read-only source facts or assessments."""
from __future__ import annotations

import unittest

from noark5_workflow.reporting.report_layout_a202 import improve_report_html


def snapshot(n=6):
    return {'jobs':[{'job_id':f'JOB-{x:03d}',
                     'extraction':f'1502_{22+x:03d} ephorte test (2005–2019)',
                     'professional_period_status':('Krever faglig vurdering – KDRS Query tilgjengelig'
                                                   if x == 2 else 'Godkjent – faglig vurdert')}
                    for x in range(1,n+1)]}


def document(inner):
    return '<!doctype html><html lang="no"><head><style>body{font-size:11pt}</style></head><body><nav>Rapport</nav><h1>Hovedrapport</h1>'+inner+'</body></html>'


def year_rows():
    return '<table><thead><tr><th>Datokilde / måltall</th><th>År</th><th>Antall</th></tr></thead><tbody>'+''.join(
        '<tr><td>'+name+'</td><td>'+str(year)+'</td><td>'+str(value)+'</td></tr>'
        for name,year,value in [('Mapper/saker (opprettet)',1899,9),
                                ('Mapper/saker (opprettet)',2005,4446),
                                ('Mapper/saker (opprettet)',2099,139),
                                ('Registreringer (opprettet)',1958,2),
                                ('Registreringer (opprettet)',2019,60321),
                                ('Journalposter (journaldato)',2005,13390),
                                ('Journalposter (journaldato)',2019,61133),
                                ('Endringslogg (ikke arkivperiode)',2019,10)])+'</tbody></table>'


class ReadabilityA202(unittest.TestCase):
    def test_job_never_wraps_and_wide_titles_split_only_headers(self):
        src=document('<table class="a20-part-index"><thead><tr>'+''.join('<th>'+x+'</th>' for x in
            ('Jobb','Uttrekk','Arkivdel','System-ID','Mapper','Registreringer','Journalposter',
             'Dokumentbeskrivelser','Dokumentobjekter','Vurderingsstatus'))+'</tr></thead><tbody>'+(
            '<tr><td>JOB-002</td><td>1502_024</td><td>Landbrukssaker</td><td>12345678-abcd-1111-2222-ffffffffffaa</td>'
            '<td>0</td><td>8</td><td>6</td><td>9</td><td>10</td><td>Ikke faglig godkjent</td></tr>')+'</tbody></table>')
        out=improve_report_html(src,'vedlegg-b-arkivdeler.html',snapshot())
        self.assertIn('class="report-job-id"',out)
        self.assertIn('white-space:nowrap !important',out)
        self.assertIn('class="report-table-scroll"',out)
        self.assertIn('Dokument<br>beskrivelser',out)
        self.assertIn('<td class="report-number">0</td>',out)
        self.assertIn('Landbrukssaker',out)
        self.assertIn('12345678-abcd-1111-2222-ffffffffffaa',out)
        self.assertNotIn('<td>JOB-002</td>',out)
        self.assertIn('a20-part-index report-job-table report-wide-table',out)

    def test_43_archive_parts_are_collapsed_but_kept_in_main_report(self):
        names=[f'Arkivdel {i}' for i in range(1,44)]
        src=document('<table class="job-overview"><thead><tr>'+''.join('<th>'+h+'</th>' for h in
            ('Jobb','Uttrekk','Arkivdel(er)','Periodevurdering','Periodemerknad','Status','Fremdrift','Depotrapport'))+
            '</tr></thead><tbody><tr><td>JOB-002</td><td>1502_024</td><td>'+ '<br>'.join(names)+
            '</td><td>Ikke vurdert</td><td>–</td><td>Ferdig</td><td>100 %</td><td>Funnet</td></tr></tbody></table>')
        out=improve_report_html(src,'index.html',snapshot())
        self.assertIn('43 arkivdeler – vis fullstendig liste',out)
        self.assertIn('Arkivdel 43',out)
        self.assertIn('Arkivdel 1',out)
        self.assertEqual(out.count('<summary>43 arkivdeler'),1)

    def test_d_keep_source_specific_years_and_true_zero_not_inferred(self):
        raw=year_rows()
        src=document('<h2>Periodeavstemming</h2><h2>KDRS Query – importerte årsserier og periodeevidens</h2>'+
                     '<h3>JOB-002 – periodevurdering av hele uttrekket</h3>'+
                     '<table><thead><tr><th>Fra</th></tr></thead><tbody><tr><td>2005–2019</td></tr></tbody></table>'+
                     '<h4>KDRS Query standard – import 123</h4><p>Kilde: 1502_003.txt</p>'+
                     '<h4>Hele uttrekket – 1899–2099</h4>'+raw)
        out=improve_report_html(src,'vedlegg-d-periodevurdering.html',snapshot())
        self.assertIn('Mapper/saker (opprettet)',out)
        self.assertIn('1958',out)
        self.assertIn('60321',out)
        self.assertIn('2099',out)
        self.assertIn('Vis opprinnelig årsopptelling – 8 kildeverdier',out)
        self.assertIn('data-yearly=',out)
        self.assertEqual(out.count('<figure class="report-series">'),4)
        self.assertIn('Endringslogg er ikke arkivperiode.',out)
        self.assertIn('Kilde: 1502_003.txt',out)
        self.assertIn('id="d-job-002"',out)
        self.assertNotIn('1899: 0',out)

    def test_d_no_false_manual_approval_from_selected_years(self):
        original=document('<table><thead><tr><th>Jobb</th><th>Status</th><th>Godkjent/valgt</th></tr></thead>'
                          '<tbody><tr><td>JOB-002</td><td>Kan ikke vurderes</td><td>[2005, 2019]</td></tr></tbody></table>'
                          '<h2>Periodeavstemming</h2>')
        out=improve_report_html(original,'vedlegg-d-periodevurdering.html',snapshot())
        self.assertIn('Uten DWM XPath-år – faglig vurdering mulig',out)
        self.assertIn('Lagret periode (godkjent / utkast)',out)
        self.assertIn('[2005, 2019]',out)
        self.assertNotIn('Godkjent – faglig vurdert 2005–2019',out)

    def test_d_legacy_xpath_only_status_label_row_is_source_qualified(self):
        label='1502_024 ephorte test (2005–2019)'
        original=document('<section class=""><h2>Periodeavstemming</h2>'
                          '<table><thead><tr><th>Uttrekk</th><th>Avstemming</th></tr></thead>'
                          '<tbody><tr><td>'+label+'</td><td>Kan ikke vurderes</td>'
                          '</tr></tbody></table></section>')
        out=improve_report_html(original,'vedlegg-d-periodevurdering.html',snapshot())
        self.assertIn('Uten DWM XPath-år – faglig vurdering mulig',out)
        self.assertNotIn('<td>Kan ikke vurderes</td>',out)
        self.assertIn(label,out)

    def test_d_43_parts_collapsed_without_approval(self):
        cells=''.join(f'<tr><td>{i}</td><td>Arkivdel {i}</td><td>id{i}</td><td>–</td><td>–</td><td>Ikke faglig godkjent</td><td>–</td></tr>' for i in range(1,44))
        table='<table><thead><tr><th>#</th></tr></thead><tbody>'+cells+'</tbody></table>'
        html=document('<h3>JOB-002 – periodevurdering per arkivdel</h3>'+table)
        out=improve_report_html(html,'vedlegg-d-periodevurdering.html',snapshot())
        self.assertIn('43 arkivdeler; 0 faglig godkjent',out)
        self.assertIn('Vis alle 43 arkivdelvise periodestatusene',out)
        self.assertIn('Arkivdel 43',out)

    def test_c_navigation_and_u2_labels_do_not_assign_dwm_part_ids(self):
        source='<h2>Felles kontroll- og måltallssammenstilling – DWM / Arkade 5 / KDRS Query</h2>'
        for i in range(1,7):
            jid=f'JOB-{i:03d}'
            source+=f'<h3>{jid} – Arkade 5 / PRONOM / KDRS Query</h3>'
            if i==2:
                source+='<h4>KDRS Query – Standard / U1 / U2</h4>'
                source+='<table><thead><tr><th>Type</th></tr></thead><tbody><tr><td>u02</td></tr></tbody></table>'
                for n in range(1,44):
                    source+='<h4>N5.102 – Konsentrert opptelling pr. arkivdel (u02)</h4>'
                    source+=('<table><thead><tr><th>Linje</th><th>Resultat</th></tr></thead><tbody>'
                             '<tr><td>1</td><td>Arkivdel '+str(n)+': Kildeområde '+str(n)+'</td></tr>'
                             '<tr><td>2</td><td>Mappe: 12</td></tr></tbody></table>')
            source+=f'<h3>{jid} – kildematrise</h3>'
        out=improve_report_html(document(source),'vedlegg-c-teknisk-evidens.html',snapshot())
        self.assertEqual(out.count('class="report-job-heading"'),12)
        self.assertIn('c-sources-job-002',out)
        self.assertIn('c-comparison-job-006',out)
        self.assertIn('Vis KDRS Query Standard / U1 / U2 – 43 kildeområder, 43 U2-arkivdeler',out)
        self.assertIn('JOB-002 – U2 Arkivdel 13: Kildeområde 13',out)
        self.assertEqual(out.count('class="report-part-heading"'),43)
        self.assertIn('ikke automatisk koblet til DWM system-ID',out)
        self.assertIn('Kildeområde 43',out)
        self.assertEqual(out.count('class="report-job-navigation"'),2)

    def test_c_arkade_errors_remain_readable_when_full_list_is_collapsed(self):
        rows=''.join('<tr><td>N5.%02d</td><td>Test</td><td>%s</td><td>%d</td></tr>' %
                     (i,'error' if i==3 else 'ok',79 if i==3 else 0) for i in range(1,55))
        table='<table><thead><tr><th>Test</th><th>Navn</th><th>Status</th><th>Feil</th></tr></thead><tbody>'+rows+'</tbody></table>'
        original=document('<h3>JOB-001 – Arkade 5 / PRONOM / KDRS Query</h3><h4>Noark 5-tester</h4>'+table)
        out=improve_report_html(original,'vedlegg-c-teknisk-evidens.html',snapshot())
        self.assertIn('N5.03 (79 feil)',out)
        self.assertIn('Noark 5-tester – 54 kontroller, 1 med feil',out)
        self.assertIn('N5.54',out)

    def test_c_empty_kdrs_source_is_visible_not_collapsed(self):
        src=document('<h3>JOB-001 – Arkade 5 / PRONOM / KDRS Query</h3>'
                     '<h4>KDRS Query – Standard / U1 / U2</h4>'
                     '<p>Ingen KDRS Query-resultater tilgjengelige for denne jobben.</p>')
        out=improve_report_html(src,'vedlegg-c-teknisk-evidens.html',snapshot())
        self.assertIn('Ingen KDRS Query-resultater tilgjengelige',out)
        self.assertNotIn('<details class="report-fold report-source-group">',out)

    def test_28_jobs_navigation_still_separate(self):
        s=snapshot(28)
        headings=''.join(f'<h3>JOB-{i:03d} – Arkade 5 / PRONOM / KDRS Query</h3><p>Kilde {i}</p>' for i in range(1,29))
        out=improve_report_html(document(headings),'vedlegg-c-teknisk-evidens.html',s)
        self.assertIn('JOB-028',out)
        self.assertEqual(out.count('class="report-job-heading"'),28)
        self.assertEqual(out.count('href="#c-sources-job-'),28)


if __name__=='__main__':
    unittest.main()
