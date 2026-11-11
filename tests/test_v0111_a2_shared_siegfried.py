"""DWM must reuse existing SIARD-managed Siegfried without changing it."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.siegfried_shared_v0111_a2 import find_siegfried_executable


class SharedSiegfriedTests(unittest.TestCase):
    def test_detects_shared_binary_in_a_child_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'siegfried'; child=root/'release'
            child.mkdir(parents=True)
            import sys
            sf=child/('sf.exe' if sys.platform=='win32' else 'sf')
            sf.write_bytes(b'placeholder')
            self.assertEqual(find_siegfried_executable(shared_root=root, include_path=False), sf.resolve())

    def test_configured_binary_preferred_without_execution(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sf=root/('sf.exe' if sys.platform=='win32' else 'sf')
            sf.write_bytes(b'placeholder')
            self.assertEqual(find_siegfried_executable(str(sf),shared_root=root/'absent', include_path=False), sf.resolve())

    def test_missing_binary_does_not_install_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'none'
            self.assertIsNone(find_siegfried_executable(shared_root=root, include_path=False))
            self.assertFalse(root.exists())


if __name__=='__main__':
    unittest.main()
