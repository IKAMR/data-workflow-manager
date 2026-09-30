from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_control_workspace_is_presented_in_front_without_permanent_topmost():
    text = (ROOT / 'gui' / 'depot_result_center_a22_3.py').read_text(encoding='utf-8')
    assert 'def _a223_present_work_window' in text
    assert 'win.lift()' in text
    assert 'win.focus_force()' in text
    assert 'win.attributes("-topmost", True)' in text
    assert 'win.attributes("-topmost", False)' in text
    assert 'win.after(40, lambda: self._a223_present_work_window(win))' in text


def test_pronom_headers_use_real_buttons_so_count_sort_is_clickable():
    text = (ROOT / 'gui' / 'depot_result_center_a21_17.py').read_text(encoding='utf-8')
    assert '("count", "Antall")' in text
    assert 'label = ctk.CTkButton(' in text
    assert 'command=lambda k=key: set_sort(k)' in text
    assert 'state = {"key": "count", "reverse": True}' in text
