import unittest
import sys
import types
# Standalone delta test: the complete repository supplies result_bank at runtime.
if "noark5_workflow.external_evidence.result_bank" not in sys.modules:
    module=types.ModuleType("noark5_workflow.external_evidence.result_bank")
    module.build_external_result_bank=lambda *a,**k: {}
    sys.modules[module.__name__]=module
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from noark5_workflow.external_evidence.kdrs_query_selection import candidates
from noark5_workflow.external_evidence.kdrs_query_views import presentation_text, render_kdrs_query_html
from noark5_workflow.external_evidence.legacy_layout_a410 import audit_legacy_layout

POOL={'resources':[{'resource_id':'r1','report_type':'standard','source_file':'example.txt','source_sha256':'abc','test_id':'C08','semantic_lines':[{'line_number':1,'archive_part_index':None,'raw_text':'N5.10 Mapper pr. type; Alle: 66834','facts':[{'metric_id':'folder_count','value':66834,'value_kind':'count','mapping_status':'exact','label':'Mapper'}]},{'line_number':2,'archive_part_index':3,'raw_text':'Elektr: 49926','facts':[{'metric_id':'folder_count','value':49926,'value_kind':'count','mapping_status':'exact'}]},{'line_number':3,'archive_part_index':None,'raw_text':'Elektr: 5995','facts':[{'metric_id':None,'value':5995,'value_kind':'labelled_count','mapping_status':'context_only'}]}]}]}
class SafetyTests(unittest.TestCase):
    @patch('noark5_workflow.external_evidence.kdrs_query_mapping.build_mapped_pool',return_value=POOL)
    def test_candidates_are_exact_and_whole_only(self,_):
        self.assertEqual([r['value'] for r in candidates('.', 'folder_count')],[66834])
        self.assertEqual(candidates('.', 'document_object_count'),[])
    def test_delimiter_preserves_source(self):
        raw='Elektr: 49926, @@\n@@ )'
        self.assertNotIn('@@',presentation_text(raw))
        self.assertIn('@@',raw)
        data={'resources':[{'report_type':'standard','observations':[{'line':1,'text':raw}]}]}
        self.assertNotIn('@@',render_kdrs_query_html(data))
    def test_inventory_is_non_destructive(self):
        with TemporaryDirectory() as root:
            p=Path(root);(p/'metadata').mkdir();(p/'dwm/metadata').mkdir(parents=True)
            (p/'metadata/depot_metadata.json').write_text('old')
            (p/'dwm/metadata/depot_metadata.json').write_text('new')
            result=audit_legacy_layout(p)
            self.assertFalse(result['items'][0]['safe_to_automatically_remove'])
            self.assertNotEqual(result['items'][0]['legacy_sha256'],result['items'][0]['active_sha256'])
            self.assertEqual((p/'metadata/depot_metadata.json').read_text(),'old')
if __name__=='__main__': unittest.main()
