"""v0.1.13-a1 fix3: isolate native Qt crash in experimental result views.

Keep the tested Basic operation-order improvement. Until the result-center
extension has passed Windows native lifecycle tests, use the unchanged
v0.1.12 ResultCenterWindow implementation. No Work or job file is modified.
"""
from __future__ import annotations


def install() -> None:
    from app.basic_order_v0113_a1 import install_basic_order

    install_basic_order()
    # Deliberately do NOT patch result_center_siegfried_v0111_a3.ResultCenterWindow.
    # The a1 GUI mixin is disabled because it causes a native Qt access violation
    # on opening Resultatvisninger. Existing v0.1.12 result tabs remain intact.
