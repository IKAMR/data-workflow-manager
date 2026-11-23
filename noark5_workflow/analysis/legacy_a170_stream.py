"""Bounded-memory legacy A170 compatibility analysis for the U1/U2 definition.

Preserves the v1 output shape without evaluating global XPath node sets.
Only the explicitly supported definition subset is accepted. A failed analysis
is *never* emitted as a successful/partial result.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from lxml import etree
from noark5_workflow.analysis.definition_engine import AnalysisDefinitionError, load_analysis_definition

_TAG = re.compile(r"local-name\(\)\s*=\s*(['\"])([^'\"]+)\1")


def _tag_from_xpath(expression: str, *, kind: str) -> str:
    expr = str(expression)
    found = _TAG.findall(expr)
    # A170's v1 definition has exactly one local-name for simple selectors,
    # field paths and descendants. An ancestor reference has two and is
    # implemented explicitly below rather than guessed from the last token.
    if kind == 'ancestor':
        if len(found) == 2 and 'ancestor::' in expr and 'string(' in expr:
            return found[-1][1]
    elif len(found) == 1 and ('local-name()' in expr):
        if kind == 'count' and not expr.startswith('count(.//*'):
            pass
        elif kind == 'select' and not ('//*' in expr or './/*' in expr):
            pass
        elif kind == 'field' and not expr.startswith('string(./*'):
            pass
        else:
            return found[0][1]
    raise AnalysisDefinitionError(f'A170-strømmeplan støtter ikke {kind}-XPath: {expr}')


def _plan(definition: dict[str, Any]) -> dict[str, Any]:
    planned = {}
    for entity in definition['entities']:
        entity_id = str(entity['id'])
        fields = {}
        ancestors = {}
        for field_id, expression in entity.get('fields', {}).items():
            if 'ancestor::' in expression:
                ancestors[field_id] = _tag_from_xpath(expression, kind='ancestor')
            else:
                fields[field_id] = _tag_from_xpath(expression, kind='field')
        metrics = {}
        for metric in entity.get('metrics', []):
            metrics[metric['id']] = _tag_from_xpath(metric['expression'], kind='count')
            if metric.get('type') != 'integer':
                raise AnalysisDefinitionError('A170-strømming støtter bare heltallsmetrikker.')
        children = {}
        for child in entity.get('children', []):
            children[child['id']] = {
                'tag': _tag_from_xpath(child['select'], kind='select'),
                'fields': {f: _tag_from_xpath(x, kind='field') for f, x in child.get('fields', {}).items()},
            }
        planned[entity_id] = {
            'tag': _tag_from_xpath(entity['select'], kind='select'),
            'fields': fields, 'ancestor_fields': ancestors,
            'metrics': metrics, 'children': children,
        }
    if set(planned) != {'archive', 'archive_part'}:
        raise AnalysisDefinitionError('Uventet A170-entity-sett: ' + str(sorted(planned)))
    return planned


def run_legacy_a170_stream(xml_path: str | Path, definition_path: str | Path) -> dict[str, Any]:
    """Produce the historical A170 JSON model using bounded-memory iterparse."""
    path = Path(xml_path)
    definition = load_analysis_definition(definition_path)
    plan = _plan(definition)
    result: dict[str, list[dict[str, Any]]] = {key: [] for key in plan}
    active: dict[str, list[dict[str, Any]]] = {key: [] for key in plan}
    active_children: list[dict[str, Any]] = []
    stack: list[str] = []
    try:
        for event, element in etree.iterparse(str(path), events=('start', 'end'),
                                                resolve_entities=False, no_network=True,
                                                huge_tree=True):
            tag = etree.QName(element).localname
            if event == 'start':
                stack.append(tag)
                for entity_id, cfg in plan.items():
                    if tag == cfg['tag']:
                        parent_archive = active['archive'][-1] if active['archive'] else None
                        state = {'index': len(result[entity_id]) + len(active[entity_id]) + 1,
                                 'fields': {}, 'metrics': {k: 0 for k in cfg['metrics']},
                                 'children': {k: [] for k in cfg['children']},
                                 '_parent_archive': parent_archive}
                        active[entity_id].append(state)
                # Descendant counts include the element itself if it happens
                # to have the same name as a metric's target (XPath .//* excludes self).
                for entity_id, cfg in plan.items():
                    for state in active[entity_id]:
                        for metric_id, metric_tag in cfg['metrics'].items():
                            if tag == metric_tag and len(stack) > 1:
                                state['metrics'][metric_id] += 1
                for entity_id, cfg in plan.items():
                    if not active[entity_id]:
                        continue
                    for child_id, child in cfg['children'].items():
                        if tag == child['tag']:
                            active_children.append({'tag': tag, 'depth': len(stack),
                                                    'owner': active[entity_id][-1],
                                                    'id': child_id, 'fields': {}, 'mapping': child['fields']})
                continue

            parent_tag = stack[-2] if len(stack) >= 2 else None
            for entity_id, cfg in plan.items():
                if active[entity_id] and parent_tag == cfg['tag']:
                    for field_id, field_tag in cfg['fields'].items():
                        if tag == field_tag:
                            active[entity_id][-1]['fields'][field_id] = ''.join(element.itertext()).strip()
            for child in active_children:
                if len(stack) == child['depth'] + 1 and parent_tag == child['tag']:
                    for field_id, field_tag in child['mapping'].items():
                        if tag == field_tag:
                            child['fields'][field_id] = ''.join(element.itertext()).strip()
            for child in list(active_children):
                if tag == child['tag'] and len(stack) == child['depth']:
                    for field_id in child['mapping']:
                        child['fields'].setdefault(field_id, '')
                    rows = child['owner']['children'][child['id']]
                    rows.append({'index': len(rows) + 1, 'fields': child['fields']})
                    active_children.remove(child)
            for entity_id, cfg in plan.items():
                if tag == cfg['tag'] and active[entity_id]:
                    state = active[entity_id].pop()
                    for field_id in cfg['fields']:
                        state['fields'].setdefault(field_id, '')
                    # Archive metadata may occur after its archive parts. Keep
                    # a reference until the entire XML stream has completed.
                    result[entity_id].append(state)
            stack.pop()
            element.clear()
            parent = element.getparent()
            if parent is not None:
                while element.getprevious() is not None:
                    del parent[0]
    except (etree.XMLSyntaxError, OSError) as exc:
        raise AnalysisDefinitionError(f'A170-strømming feilet: {type(exc).__name__}: {exc}') from exc

    # Resolve ancestor fields after streaming, using the actual owning archive.
    for entity_id, cfg in plan.items():
        for position, state in enumerate(result[entity_id], start=1):
            if cfg['ancestor_fields']:
                parent = state['_parent_archive']
                for field_id, ancestor_tag in cfg['ancestor_fields'].items():
                    if parent is None:
                        state['fields'][field_id] = ''
                    else:
                        field_id_in_parent = next((f for f, t in plan['archive']['fields'].items()
                                                   if t == ancestor_tag), None)
                        if field_id_in_parent is None:
                            raise AnalysisDefinitionError('Ukjent arkiv-ancestor-felt: ' + ancestor_tag)
                        state['fields'][field_id] = parent['fields'].get(field_id_in_parent, '')
            state.pop('_parent_archive')
            state['index'] = position
    return {
        'model_format_version': 1,
        'definition_id': definition['definition_id'],
        'definition_path': str(Path(definition_path).resolve()),
        'source': str(path.resolve()),
        'basis': definition.get('basis', {}),
        'summary': {'entity_counts': {key: len(value) for key, value in result.items()}},
        'entities': result,
    }
