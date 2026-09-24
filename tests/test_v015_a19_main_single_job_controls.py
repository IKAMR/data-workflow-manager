from pathlib import Path
import unittest
class Tests(unittest.TestCase):
 def test_controls(self):
  t=(Path(__file__).resolve().parents[1]/'gui/persistent_app_a54.py').read_text(encoding='utf-8')
  for x in ['Åpne jobbliste','Lagre jobbliste','Lagre som...','command=self._open_job_list_dialog','command=self._save_job_list','command=self._save_job_list_as']: self.assertIn(x,t)
  self.assertNotIn('_set_output_subfolder_rule(',t)
 def test_runtime(self):
  t=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf-8'); self.assertIn('from gui.persistent_app_a54 import run_gui',t)
if __name__=='__main__': unittest.main()
