"""a17: bounded-memory XPath catalogue projection for very large arkivstruktur.xml.

This evaluator refuses unsupported syntax instead of manufacturing apparently
successful archive-control results. A single streaming scan is shared by the
catalogue's metric tests and archive-part subsets. Original engine is used for
small sources; C01/C02 retain the validated a13 iterator implementation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
import re
from typing import Any

from lxml import etree

# Do not attempt etree.parse() + full deep copy of a multi-GB source.
LARGE_XML_THRESHOLD = 512 * 1024 * 1024


class UnsupportedStreamMetric(ValueError):
    pass


def _split_path(path: str):
    """Parse a safe subset of XPath location paths preserving / versus //."""
    value = path.strip()
    relative = value.startswith('.')
    if relative:
        value = value[1:]
    if not value.startswith('/'):
        # Direct children of the context node, e.g. 'opprettetDato'.
        value = '/' + value
    steps = []
    axis = 'child'
    index = 0
    if value.startswith('//'):
        axis, index = 'desc', 2
    elif value.startswith('/'):
        index = 1
    start = index
    depth = 0
    quote = None
    while index <= len(value):
        end = index == len(value)
        if not end:
            ch = value[index]
            if ch in "\"'":
                quote = None if quote == ch else (ch if quote is None else quote)
            elif quote is None:
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
        if end or (depth == 0 and quote is None and value[index:index + 1] == '/'):
            piece = value[start:index].strip()
            if piece:
                match = re.fullmatch(r'([A-Za-z_][\w.-]*|\*|text\(\))((?:\[.*\])*)', piece)
                if not match:
                    raise UnsupportedStreamMetric('Unsupported XPath step: ' + piece)
                name, suffix = match.groups()
                preds = []
                if suffix:
                    # Independent predicates (e.g. [@type=...][dokumentflyt]).
                    # Reject nested bracket syntax, which requires a different AST.
                    if suffix.count('[') != suffix.count(']'):
                        raise UnsupportedStreamMetric('Unbalanced predicate: ' + piece)
                    pos = 0
                    while pos < len(suffix):
                        if suffix[pos] != '[':
                            raise UnsupportedStreamMetric('Unsupported predicate: ' + piece)
                        end_pred = suffix.find(']',pos+1)
                        if end_pred < 0 or '[' in suffix[pos+1:end_pred]:
                            raise UnsupportedStreamMetric('Nested predicate: ' + piece)
                        preds.append(suffix[pos+1:end_pred])
                        pos = end_pred+1
                steps.append((axis, name, preds))
            if end:
                break
            if value[index:index + 2] == '//':
                axis, index = 'desc', index + 2
            else:
                axis, index = 'child', index + 1
            start = index
            continue
        index += 1
    if not steps:
        raise UnsupportedStreamMetric('Empty XPath: ' + path)
    if not relative and path.startswith('//'):
        # XPath // includes the document element itself.
        pass
    return relative, steps


def _frame_element(frame):
    """Tiny synthetic element for predicates, never a full XML subtree."""
    node = etree.Element(frame['tag'], attrib=frame['attrs'])
    for name in frame['children']:
        if not name:
            continue
        child = etree.SubElement(node, name)
        child.text = frame['values'].get(name)
    return node


def _step_match(frame, step, *, is_last=False):
    _, name, preds = step
    if name == 'text()':
        return bool(frame['text']) if is_last else False
    if name != '*' and frame['tag'] != name:
        return False
    for pred in preds:
        # Ancestor-frame child predicates cannot safely be evaluated before
        # the ancestor has finished; callers reject them at compile time.
        try:
            if not _frame_element(frame).xpath('boolean(self::*[' + pred + '])'):
                return False
        except etree.XPathError as exc:
            raise UnsupportedStreamMetric('Unsupported XPath predicate: ' + pred) from exc
    return True


class Selector:
    def __init__(self, path: str):
        self.path = path
        self.relative, self.steps = _split_path(path)
        self.final = self.steps[-1][1]
        self.is_text = self.final == 'text()'
        # Predicates on ancestors that depend on child content can be false
        # until the ancestor's closing tag. Such paths need a dedicated handler.
        for _, _, preds in self.steps[:-1]:
            if preds and not all(re.fullmatch(r'@\w+\s*=\s*[\"\'].*[\"\']', p) for p in preds):
                raise UnsupportedStreamMetric('Ancestor predicate needs a deferred evaluator: ' + path)

    def matches(self, stack, current_part_depth):
        if not stack:
            return False
        # For text() the last step is a text child of the current element.
        nodes = stack
        steps = self.steps[:-1] if self.is_text else self.steps
        if not steps:
            return False
        if self.relative and current_part_depth is None:
            return False
        if self.relative and len(stack) - 1 <= current_part_depth:
            return False
        if self.is_text and not nodes[-1]['text']:
            return False
        if not _step_match(nodes[-1], steps[-1], is_last=True):
            return False
        i = len(nodes) - 1
        for j in range(len(steps) - 2, -1, -1):
            axis = steps[j + 1][0]
            if axis == 'child':
                i -= 1
                if i < 0 or not _step_match(nodes[i], steps[j]):
                    return False
            else:
                i -= 1
                while i >= 0 and not _step_match(nodes[i], steps[j]):
                    i -= 1
                if i < 0:
                    return False
        first_axis = steps[0][0]
        if self.relative:
            if first_axis == 'child':
                return i == current_part_depth + 1
            return i > current_part_depth
        if first_axis == 'child':
            return i == 0
        return True


def _count_paths(expression: str):
    """Only additive/subtractive count() expressions, exact XPath operands."""
    value = expression.strip()
    # Count expressions can contain nested count(@*) inside a predicate.
    out = []
    pos = 0
    while pos < len(value):
        while pos < len(value) and value[pos].isspace():
            pos += 1
        sign = 1
        if pos < len(value) and value[pos] in '+-':
            sign = -1 if value[pos] == '-' else 1
            pos += 1
        while pos < len(value) and value[pos].isspace():
            pos += 1
        if value[pos:pos + 6] != 'count(':
            raise UnsupportedStreamMetric('Not a sum of count() expressions: ' + expression)
        pos += 6
        start = pos
        depth = 1
        while pos < len(value) and depth:
            if value[pos] == '(':
                depth += 1
            elif value[pos] == ')':
                depth -= 1
            pos += 1
        if depth:
            raise UnsupportedStreamMetric('Unbalanced count(): ' + expression)
        out.append((sign, value[start:pos - 1]))
    return out


class Metric:
    def __init__(self, definition: dict):
        self.spec = definition
        self.id = definition['id']
        self.type = definition.get('type', 'xpath')
        self.paths = _count_paths(definition['expression']) if self.type == 'xpath' else [(1, definition['select'])]
        self.selectors = []
        deferred_expr = definition.get('expression','').replace(' ','')
        is_deferred = deferred_expr in {
            'count(//klasse[klasse]/mappe)', 'count(.//klasse[klasse]/mappe)',
            'count(//registrering[not(dokumentbeskrivelse)]/registreringsID)',
            'count(//dokumentbeskrivelse[not(dokumentobjekt)]/systemID/text())',
            'count(.//dokumentbeskrivelse[not(dokumentobjekt)]/systemID/text())'}
        if not is_deferred:
            self.selectors = [(sign, Selector(path)) for sign, path in self.paths]
        self.counts = [0] * len(self.paths)
        self.counter = Counter()
        self.first = self.last = None
        self.numeric_count = 0
        self.numeric_sum = 0.0
        self.numeric_min = self.numeric_max = None
        self.buckets = Counter()
        self.rows = []
        self.deferred = None
        if self.type == 'xpath' and len(self.paths) == 1:
            expression = self.spec['expression'].replace(' ', '')
            deferred = {
                'count(//klasse[klasse]/mappe)': ('klasse', 'klasse', 'mappe'),
                'count(.//klasse[klasse]/mappe)': ('klasse', 'klasse', 'mappe'),
                'count(//registrering[not(dokumentbeskrivelse)]/registreringsID)': ('registrering', '!dokumentbeskrivelse', 'registreringsID'),
                'count(//dokumentbeskrivelse[not(dokumentobjekt)]/systemID/text())': ('dokumentbeskrivelse', '!dokumentobjekt', 'systemID#text'),
                'count(.//dokumentbeskrivelse[not(dokumentobjekt)]/systemID/text())': ('dokumentbeskrivelse', '!dokumentobjekt', 'systemID#text'),
            }
            self.deferred = deferred.get(expression)
        if self.type in {'group_xpath','year_counts_by_node'}:
            expr = definition.get('value')
            allowed = {'name(..)','string(ancestor::dokumentbeskrivelse[1]/opprettetDato)'}
            if expr not in allowed or (self.type == 'year_counts_by_node' and expr != 'string(ancestor::dokumentbeskrivelse[1]/opprettetDato)'):
                raise UnsupportedStreamMetric('Unverified XPath node-group expression: '+str(expr))
        if self.type == 'group_attr' and definition.get('value','@type') != '@type':
            raise UnsupportedStreamMetric('Unverified grouping attribute: '+str(definition.get('value')))
        if self.type not in {'xpath','group_text','group_attr','group_xpath','year_counts',
                              'year_counts_by_node','date_range','numeric_stats','numeric_buckets'}:
            raise UnsupportedStreamMetric('Metric type requires dedicated streaming implementation: ' + self.type)

    def observe(self, stack, part_depth):
        frame = stack[-1]
        if self.deferred is not None:
            target, condition, child = self.deferred
            if frame['tag'] != target or (part_depth is not None and len(stack)-1 <= part_depth):
                return
            has = bool(frame['children'][condition.lstrip('!')])
            if condition.startswith('!'):
                has = not has
            if has:
                name = child.split('#', 1)[0]
                if frame['children'][name] and ('#text' not in child or frame['values'].get(name)):
                    self.counts[0] += frame['children'][name]
            return
        if self.type in ('group_xpath','year_counts_by_node') and self.spec.get('value') == 'string(ancestor::dokumentbeskrivelse[1]/opprettetDato)':
            if frame['tag'] != 'dokumentbeskrivelse' or (part_depth is not None and len(stack)-1 <= part_depth):
                return
            value = frame['values'].get('opprettetDato','').strip()
            quantity = frame.get('document_objects',0)
            if not value or not quantity:
                return
            if self.type == 'year_counts_by_node':
                if len(value) >= 4:
                    self.counter[value[:4]] += quantity
            else:
                self.counter[value] += quantity
            return
        matched = []
        for index, (sign, selector) in enumerate(self.selectors):
            if selector.final not in (frame['tag'], '*', 'text()'):
                continue
            if selector.matches(stack, part_depth):
                matched.append(index)
        if not matched:
            return
        if self.type == 'group_xpath' and self.spec.get('value') == 'name(..)':
            if len(stack) >= 2:
                self.counter[stack[-2]['tag']] += 1
            return
        if self.type == 'xpath':
            for i in matched:
                self.counts[i] += 1
            return
        value = frame['text'].strip()
        if self.type == 'group_attr':
            name = str(self.spec.get('value','@type')).lstrip('@')
            value = str(frame['attrs'].get(name,'')).strip()
        if self.type in ('group_text','group_attr'):
            if value:
                self.counter[value] += 1
        elif self.type == 'year_counts':
            if len(value) >= 4:
                self.counter[value[:4]] += 1
        elif self.type == 'date_range':
            if len(value) >= 10:
                date = value[:10]
                if self.first is None or date < self.first:
                    self.first = date
                if self.last is None or date > self.last:
                    self.last = date
        elif self.type in ('numeric_stats','numeric_buckets'):
            try:
                num = float(value)
            except ValueError:
                return
            if self.type == 'numeric_stats':
                self.numeric_count += 1
                self.numeric_sum += num
                self.numeric_min = num if self.numeric_min is None else min(num, self.numeric_min)
                self.numeric_max = num if self.numeric_max is None else max(num, self.numeric_max)
            else:
                for b in self.spec.get('buckets',[]):
                    low, high = b.get('min'), b.get('max')
                    if (low is None or num >= low) and (high is None or num <= high):
                        self.buckets[b['id']] += 1

    def result(self):
        if self.type == 'xpath':
            return sum(sign * self.counts[i] for i,(sign,_) in enumerate(self.paths))
        if self.type in ('group_text','group_attr','group_xpath','year_counts_by_node'):
            return dict(sorted(self.counter.items(), key=lambda x:x[0].casefold()))
        if self.type == 'year_counts':
            return dict(sorted(self.counter.items()))
        if self.type == 'date_range':
            return {'first':self.first,'last':self.last}
        if self.type == 'numeric_buckets':
            return {b['id']:self.buckets[b['id']] for b in self.spec.get('buckets',[])}
        if self.type == 'numeric_stats':
            if not self.numeric_count:
                return {'count':0,'sum':0,'average':None,'min':None,'max':None}
            total = self.numeric_sum
            def normal(v):
                return int(v) if v.is_integer() else v
            return {'count':self.numeric_count,'sum':normal(total),
                    'average':total/self.numeric_count,'min':normal(self.numeric_min),
                    'max':normal(self.numeric_max)}
        raise AssertionError(self.type)


def _special_part_specs(kind):
    """Exact metric definitions of the 2026 KDRS special per-part handlers."""
    count = lambda name, expr: {'id':name,'type':'xpath','expression':'count(.//' + expr + ')'}
    group = lambda name, select: {'id':name,'type':'group_text','select':'.//' + select}
    year = lambda select: {'id':'per_year','type':'year_counts','select':'.//' + select}
    by_kind = {
        'u2_archive_parts': [count('folder_count','mappe'), count('registration_count','registrering'),
            count('document_description_count','dokumentbeskrivelse'),count('document_object_count','dokumentobjekt'),
            count('classification_system_count','klassifikasjonssystem'),count('class_count','klasse'),
            {'id':'folder_type_counts','type':'group_attr','select':'.//mappe','value':'@type'},
            group('folder_status_counts','mappe/saksstatus'), group('journalpost_type_counts','registrering/journalposttype'),
            group('journal_status_counts','registrering/journalstatus'),
            group('document_status_counts','dokumentbeskrivelse/dokumentstatus'),
            group('document_medium_counts','dokumentbeskrivelse/dokumentmedium'),
            group('variant_format_counts','dokumentobjekt/variantformat'),
            *[count(name,path) for name,path in (
                ('correspondence_party_count','korrespondansepart'),('sakspart_count','sakspart'),('part_count','part'),
                ('writeoff_count','avskrivningsmaate'),('screening_count','skjerming'),('disposal_count','kassasjon'),
                ('performed_disposal_count','utfoertKassasjon'),('deletion_count','sletting'))]],
        'classification_per_archive_part': [count(name,tag) for name,tag in (
            ('classification_system_count','klassifikasjonssystem'),('class_count','klasse'),
            ('folder_count','mappe'),('document_description_count','dokumentbeskrivelse'),
            ('document_object_count','dokumentobjekt'),('part_count','part'))],
        'year_per_archive_part': [year('mappe/opprettetDato')],
        'registration_created_year_per_archive_part': [year('registrering/opprettetDato')],
        'registration_journal_year_per_archive_part': [year('registrering/journaldato')],
        'class_folder_conflict_per_archive_part': [count('class_with_subclass_and_folder','klasse[klasse]/mappe')],
        'folder_status_per_archive_part': [count('folder_count','mappe'),group('status_counts','mappe/saksstatus'),
            count('meeting_folder_count','mappe[@type="moetemappe"]')],
        'journalpost_type_per_archive_part': [group('journalpost_type_counts','registrering/journalposttype')],
        'empty_class_per_archive_part': [count('empty_class_count','klasse[not(klasse or mappe or registrering)]')],
    }
    return by_kind.get(kind)


class StreamPlan:
    def __init__(self, tests):
        self.tests = tests
        self.whole = {}
        self.part = {}
        self.unsupported = {}
        for test in tests:
            test_id = test['test_id']
            if test_id in ('kdrs.c01','kdrs.c02'):
                continue
            execution = test.get('execution') or {}
            kind = execution.get('kind')
            special = _special_part_specs(kind)
            if kind != 'metrics' and special is None:
                if kind in {'u1_total','cross_file_journal_date_comparison',
                            'class_folder_list','empty_class_list',
                            'class_registration_conflict_list','class_registration_list'}:
                    self.whole[test_id] = []
                    self.part[test_id] = []
                    continue
                self.unsupported[test_id] = 'Special handler must have an explicit streaming equivalent: ' + str(kind)
                continue
            try:
                self.whole[test_id] = [Metric(s) for s in execution.get('metrics',[])] if kind=='metrics' else []
                self.part[test_id] = list(execution.get('archive_part_metrics',[])) if kind=='metrics' else special
                # Reject the entire test upfront if any metric is unsupported.
                for s in self.part[test_id]:
                    Metric(s)
            except UnsupportedStreamMetric as exc:
                self.unsupported[test_id] = str(exc)
                self.whole.pop(test_id,None)
                self.part.pop(test_id,None)
        self.part_values = defaultdict(list)
        self.cross_metric = None
        for t in tests:
            if t.get('execution',{}).get('kind')=='cross_file_journal_date_comparison':
                for ref in t['execution'].get('sources',{}).values():
                    if ref.get('source_xml')=='arkivstruktur.xml':
                        self.cross_metric = Metric({'id':'cross_date','type':'date_range',
                                                    'select':ref['select']})
                        break
        self.special_values = {
            'class_folder_list': {'classes':[]},
            'empty_class_list': {'classes':[]},
            'class_registration_conflict_list': {'registrations':[]},
            'class_registration_list': {'classes':[]},
        }
        self.part_order = []
        self.whole_by_tag = defaultdict(list)
        if self.cross_metric is not None:
            self.whole_by_tag[self.cross_metric.selectors[0][1].final].append(self.cross_metric)
        for metrics in self.whole.values():
            for metric in metrics:
                if metric.deferred:
                    self.whole_by_tag[metric.deferred[0]].append(metric)
                elif metric.type in ('group_xpath','year_counts_by_node') and metric.spec.get('value')=='string(ancestor::dokumentbeskrivelse[1]/opprettetDato)':
                    self.whole_by_tag['dokumentbeskrivelse'].append(metric)
                else:
                    for selector in (s for _,s in metric.selectors):
                        tag = selector.steps[-2][1] if selector.is_text and len(selector.steps) >= 2 else selector.final
                        if metric not in self.whole_by_tag[tag]:
                            self.whole_by_tag[tag].append(metric)

    def scan(self, source: Path, *, progress_path: Path | None = None):
        # JSON progress is Work evidence, never an edit to Source.
        if progress_path is not None:
            progress_path = Path(progress_path)
            progress_path.parent.mkdir(parents=True, exist_ok=True)
        visited = 0
        started_at = datetime.now().astimezone().isoformat(timespec='seconds')
        part_metrics = {}
        part_depth = None
        active_id = None
        stack = []
        context = etree.iterparse(str(source),events=('start','end'),
                                  resolve_entities=False,no_network=True,huge_tree=True)
        for event, elem in context:
            if event == 'end':
                visited += 1
                if progress_path is not None and visited % 250000 == 0:
                    import json
                    progress_path.write_text(json.dumps({
                        'format_version':1,'stage':'streaming',
                        'started_at':started_at,'elements_processed':visited,
                        'source_xml':source.name},ensure_ascii=False) + '\n',encoding='utf-8')
            if event == 'start':
                tag = etree.QName(elem).localname if isinstance(elem.tag,str) else ''
                if tag == 'arkivdel':
                    active_id = len(self.part_order) + 1
                    part_depth = len(stack)
                    self.part_order.append(active_id)
                    part_metrics = {tid:[Metric(s) for s in defs] for tid,defs in self.part.items()}
                    part_by_tag = defaultdict(list)
                    for metrics in part_metrics.values():
                        for metric in metrics:
                            if metric.deferred:
                                part_by_tag[metric.deferred[0]].append(metric)
                            elif metric.type in ('group_xpath','year_counts_by_node') and metric.spec.get('value')=='string(ancestor::dokumentbeskrivelse[1]/opprettetDato)':
                                part_by_tag['dokumentbeskrivelse'].append(metric)
                            else:
                                for selector in (s for _,s in metric.selectors):
                                    keytag = selector.steps[-2][1] if selector.is_text and len(selector.steps) >= 2 else selector.final
                                    if metric not in part_by_tag[keytag]:
                                        part_by_tag[keytag].append(metric)
                stack.append({'tag':tag,'attrs':{etree.QName(k).localname if k.startswith('{') else k:v for k,v in elem.attrib.items()},
                              'children':Counter(),'values':{},'text':''})
                continue
            if not stack:
                raise RuntimeError('Invalid XML stream nesting')
            frame = stack[-1]
            if not frame['tag']:
                stack.pop()
                elem.clear()
                continue
            frame['text'] = ''.join(elem.itertext()).strip() if len(elem)==0 else (elem.text or '').strip()
            # The element's direct children have been released from the XML
            # parser, but children/values are retained in the small frame.
            for metric in self.whole_by_tag.get(frame['tag'], ()):
                metric.observe(stack, None)
            for metric in self.whole_by_tag.get('*', ()):
                metric.observe(stack, None)
            if part_depth is not None:
                for metric in part_by_tag.get(frame['tag'], ()):
                    metric.observe(stack, part_depth)
                for metric in part_by_tag.get('*', ()):
                    metric.observe(stack, part_depth)
            if frame['tag'] == 'registrering' and len(stack) > 1 and stack[-2]['tag'] == 'klasse':
                stack[-2].setdefault('direct_registration_ids',[]).append(frame['values'].get('systemID',''))
            if frame['tag'] == 'klasse':
                title = frame['values'].get('tittel','')
                class_id = frame['values'].get('klasseID','')
                if frame['children']['mappe']:
                    self.special_values['class_folder_list']['classes'].append({
                        'class_id':class_id,'title':title,'folder_count':frame['children']['mappe']})
                if not frame['children']['klasse'] and not frame['children']['mappe']:
                    self.special_values['empty_class_list']['classes'].append({
                        'class_id':class_id,'title':title})
                if frame['children']['registrering']:
                    self.special_values['class_registration_list']['classes'].append({
                        'class_id':class_id,'title':title,
                        'registration_count':frame['children']['registrering']})
                if frame['children']['klasse'] and frame.get('direct_registration_ids'):
                    if len(stack) > 1:
                        stack[-2].setdefault('_pending_conflicts',[]).extend(frame['direct_registration_ids'])
            if frame.get('_pending_conflicts'):
                parent_class_id = frame['values'].get('klasseID','')
                for registration_id in frame['_pending_conflicts']:
                    self.special_values['class_registration_conflict_list']['registrations'].append({
                        'class_id':parent_class_id,'system_id':registration_id})
            if frame['tag'] == 'arkivdel':
                identity = {'index':active_id,'system_id':frame['values'].get('systemID',''),
                            'title':frame['values'].get('tittel',''),
                            'status':frame['values'].get('arkivdelstatus','')}
                for tid, metrics in part_metrics.items():
                    self.part_values[tid].append({'archive_part':identity,
                                                  'values':{m.id:m.result() for m in metrics}})
                active_id = None
                part_depth = None
            stack.pop()
            if stack:
                parent = stack[-1]
                parent['children'][frame['tag']] += 1
                if frame['tag']=='dokumentobjekt':
                    for ancestor in reversed(stack):
                        if ancestor['tag']=='dokumentbeskrivelse':
                            ancestor['document_objects'] = ancestor.get('document_objects',0) + 1
                            break
                if not frame['children'] or frame['tag'] in {'opprettetDato','avsluttetDato','systemID','tittel','arkivdelstatus'}:
                    parent['values'].setdefault(frame['tag'], frame['text'])
            elem.clear()
            parent_elem = elem.getparent()
            if parent_elem is not None:
                while elem.getprevious() is not None:
                    del parent_elem[0]

    def results(self):
        output = {}
        for tid, metrics in self.whole.items():
            values = {m.id:m.result() for m in metrics}
            execution = next(t['execution'] for t in self.tests if t['test_id']==tid)
            if self.part[tid]:
                rows = self.part_values[tid]
                values['_archive_parts'] = rows
                spec = execution.get('reconciliation') or []
                if spec:
                    try:
                        from . import xpath_test_engine as engine
                        values['_reconciliation'] = engine._reconcile(values, rows, spec)
                        st = [e.get('status') for e in values['_reconciliation'].values()]
                        values['_reconciliation_summary'] = {
                            'checks':len(st),'matches':st.count('match'),
                            'mismatches':st.count('mismatch'),
                            'not_comparable':st.count('not_comparable'),
                            'status':'match' if st and all(s=='match' for s in st)
                            else 'not_comparable' if st and all(s=='not_comparable' for s in st) else 'review'}
                    except Exception as exc:
                        self.unsupported[tid] = 'Reconciliation failed: '+type(exc).__name__+': '+str(exc)
                        continue
            kind = execution.get('kind')
            if kind=='cross_file_journal_date_comparison':
                values = {'_archive_date_range':self.cross_metric.result() if self.cross_metric else None}
            elif kind=='u1_total':
                values = {'_stream_u1_needed':True}
            elif kind in self.special_values:
                values = self.special_values[kind]
            elif kind != 'metrics':
                values = {'archive_parts':self.part_values[tid]}
            output[tid] = values
        return output


_CACHE: dict[tuple[str,int,int], tuple[dict,dict]] = {}


def install() -> None:
    """Install only inside the already isolated XPath worker process."""
    from . import xpath_test_engine as engine
    if getattr(engine,'_a17_streaming_installed',False):
        return
    original = engine.run_test
    original_run_catalog = engine.run_catalog
    state = {'results':{},'unsupported':{},'enabled':False,'source':None}

    def run_catalog(*args,**kwargs):
        path = Path(args[0] if args else kwargs['catalog_path'])
        extraction = Path(args[1] if len(args)>1 else kwargs['extraction_root'])
        source = extraction / 'arkivstruktur.xml'
        state.update({'results':{},'unsupported':{},'enabled':False,'source':source})
        try:
            if source.is_file() and source.stat().st_size >= LARGE_XML_THRESHOLD:
                out = Path(args[2] if len(args)>2 else kwargs['output_dir'])
                catalog = engine.load_catalog(path)
                tests = [t for t in catalog['tests'] if t.get('source_xml')=='arkivstruktur.xml']
                plan = StreamPlan(tests)
                progress_file = out / 'stream-progress-a17.json'
                plan.scan(source, progress_path=progress_file)
                prepared_results = plan.results()
                state.update({'results':prepared_results,'unsupported':plan.unsupported,'enabled':True})
                import json
                progress_file.write_text(json.dumps({
                    'format_version':1,'stage':'completed',
                    'supported_tests':len(prepared_results),
                    'unsupported_tests':plan.unsupported,
                    'source_xml':source.name},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            return original_run_catalog(*args,**kwargs)
        finally:
            state.update({'results':{},'unsupported':{},'enabled':False,'source':None})

    def run_test(test, extraction_root, standard_registry=None):
        tid = str(test.get('test_id',''))
        if not state['enabled'] or test.get('source_xml')!='arkivstruktur.xml' or tid in ('kdrs.c01','kdrs.c02'):
            return original(test,extraction_root,standard_registry=standard_registry)
        if tid not in state['results'] and tid not in state['unsupported']:
            return original(test,extraction_root,standard_registry=standard_registry)
        now = datetime.now().astimezone().isoformat(timespec='milliseconds')
        start = perf_counter()
        result = {'result_format_version':2,'test_id':tid,'definition':test,
                  'source_xml':test['source_xml'],'source_path':str(state['source']),
                  'execution_strategy':'a17-bounded-stream', 'timing':{'started_at':now}}
        if tid == 'kdrs.u01' and tid in state['results']:
            # A12 is already verified against the legacy U1 result structure.
            # Re-evaluate from Source with bounded memory instead of a full tree.
            try:
                from .u1_stream_v027_a12 import run_u1_stream
                values = run_u1_stream(state['source'])
                result.update({'status':'ok','values':values,
                               'execution_strategy':'a17-reuse-a12-u1-stream'})
            except Exception as exc:
                result.update({'status':'error','error':type(exc).__name__+': '+str(exc)})
        elif tid == 'kdrs.i02' and tid in state['results']:
            try:
                sources = test['execution']['sources']
                missing = [v['source_xml'] for v in sources.values()
                           if not (Path(extraction_root)/v['source_xml']).is_file()]
                if missing:
                    result.update({'status':'source_missing','missing_sources':missing})
                else:
                    ranges = {}
                    for name, ref in sources.items():
                        if ref['source_xml']=='arkivstruktur.xml':
                            dates = state['results'][tid]['_archive_date_range']
                        else:
                            probe = StreamPlan([{'test_id':'__date',
                                'source_xml':ref['source_xml'],
                                'execution':{'kind':'metrics','metrics':[
                                    {'id':'date','type':'date_range','select':ref['select']}]}}])
                            probe.scan(Path(extraction_root)/ref['source_xml'])
                            dates = probe.results()['__date']['date']
                        ranges[name] = {'source_xml':ref['source_xml'],'date_range':dates}
                    observed = [v['date_range'] for v in ranges.values()]
                    comparable = all(v['first'] is not None and v['last'] is not None for v in observed)
                    equal = comparable and all(v==observed[0] for v in observed[1:])
                    ranges['comparison'] = {'comparable':comparable,'all_equal':equal,
                         'status':'match' if equal else ('not_comparable' if not comparable else 'mismatch')}
                    result.update({'status':'ok','values':ranges})
            except Exception as exc:
                result.update({'status':'error','error':type(exc).__name__+': '+str(exc)})
        elif tid in state['unsupported']:
            result.update({'status':'error',
                           'error':'UnsupportedStreamMetric: '+state['unsupported'][tid]})
        else:
            values = state['results'][tid]
            try:
                checks = test.get('standard_value_checks') or []
                if checks:
                    values = dict(values)
                    values['_standard_values'] = engine._standard_value_checks(values,checks,standard_registry)
                result.update({'status':'ok','values':values})
            except Exception as exc:
                result.update({'status':'error','error':type(exc).__name__+': '+str(exc)})
        result['timing'].update({'finished_at':datetime.now().astimezone().isoformat(timespec='milliseconds'),
                                 'duration_seconds':round(perf_counter()-start,6)})
        return result

    engine.run_catalog = run_catalog
    engine.run_test = run_test
    engine._a17_streaming_installed = True
