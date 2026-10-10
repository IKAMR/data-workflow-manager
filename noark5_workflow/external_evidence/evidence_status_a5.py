"""Human-readable evidence coverage without confusing unknown with agreement."""
from __future__ import annotations
from collections import Counter


def coverage_summary(annex: dict) -> str:
    rows = [r for r in annex.get('records', []) if isinstance(r, dict)]
    selected = sum(r.get('status') == 'external_evidence_selected' for r in rows)
    comparison = Counter(r.get('dwm_comparison') or 'unknown' for r in rows)
    external = Counter(r.get('external_comparison') or 'missing' for r in rows)
    review = sum(bool(r.get('scope_review')) or r.get('status') == 'scope_review_required' for r in rows)
    fmt = lambda n: f'{n:,}'.replace(',', ' ')
    return (
        f'Evidensgrunnlag: {fmt(len(rows))} målefelt | {fmt(selected)} valgte eksterne verdier\n'
        f'DWM mot eksterne kilder: {fmt(comparison["agreement"])} samsvar | '
        f'{fmt(comparison["conflict"])} avvik | {fmt(comparison["mixed"])} blandet | '
        f'{fmt(comparison["unknown"])} ikke sammenlignbare\n'
        f'Eksterne kilder: {fmt(external["agreement"])} entydige | '
        f'{fmt(external["conflict"])} motstridende | {fmt(external["missing"])} uten observasjoner\n'
        f'{fmt(review)} omfang krever kontroll. Opprinnelig DWM-rapport er uendret.'
    )
