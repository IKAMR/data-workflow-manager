"""Read Word's *displayed* list numbering without inventing unavailable levels.

WordprocessingML numbers are often absent from w:t text; they are generated
from numbering.xml and paragraph/style numPr. This is a bounded, conservative
subset for decimal multi-level numbering, not a Word layout/rendering engine.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET
import re

W_TRANSITIONAL = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W_STRICT = 'http://purl.oclc.org/ooxml/wordprocessingml/main'
SUPPORTED_WORD_NS = frozenset((W_TRANSITIONAL, W_STRICT))


class WordNumberingResolver:
    def __init__(self, ns: str, *, styles_xml: bytes | None = None,
                 numbering_xml: bytes | None = None):
        if ns not in SUPPORTED_WORD_NS:
            raise ValueError('Ukjent WordprocessingML-navnerom')
        self.ns = ns
        self.w = lambda n: f'{{{ns}}}{n}'
        self.style_defs: dict[str, tuple[str | None, str | None, str | None]] = {}
        self.abstract: dict[str, dict[int, tuple[int,str,str]]] = {}
        self.abstract_styles: dict[str, dict[str,int]] = {}
        self.linked_styles: dict[str, tuple[str,int]] = {}
        self.concrete: dict[str, tuple[str,dict[int,int]]] = {}
        self.counters: dict[str, dict[int,int]] = {}
        self.numbered_paragraphs = 0
        self.unresolved_numbered_paragraphs = 0
        if styles_xml:
            root = ET.fromstring(styles_xml)
            for node in root.iter(self.w('style')):
                style_id = node.get(self.w('styleId'))
                if not style_id:
                    continue
                based = node.find(self.w('basedOn'))
                ppr = node.find(self.w('pPr'))
                nr = ppr.find(self.w('numPr')) if ppr is not None else None
                self.style_defs[style_id] = (
                    based.get(self.w('val')) if based is not None else None,
                    self._val(nr, 'numId'), self._val(nr, 'ilvl'))
        if numbering_xml:
            root = ET.fromstring(numbering_xml)
            for abstract in root.iter(self.w('abstractNum')):
                abstract_id = abstract.get(self.w('abstractNumId'))
                if not abstract_id:
                    continue
                levels = {}
                style_levels = {}
                for node in abstract.findall(self.w('lvl')):
                    try:
                        index = int(node.get(self.w('ilvl'), '-1'))
                        start = int(self._val(node, 'start') or '1')
                    except ValueError:
                        continue
                    if not 0 <= index <= 8 or not 0 < start < 100000:
                        continue
                    levels[index] = (start, self._val(node,'numFmt') or 'decimal',
                                     self._val(node,'lvlText') or f'%{index+1}')
                    linked_style = self._val(node,'pStyle')
                    if linked_style:
                        style_levels[linked_style] = index
                self.abstract[abstract_id] = levels
                self.abstract_styles[abstract_id] = style_levels
            for concrete in root.iter(self.w('num')):
                num_id = concrete.get(self.w('numId'))
                abstract_id = self._val(concrete, 'abstractNumId')
                if not num_id or abstract_id is None:
                    continue
                overrides = {}
                for override in concrete.findall(self.w('lvlOverride')):
                    try:
                        index = int(override.get(self.w('ilvl'), '-1'))
                        value = int(self._val(override, 'startOverride') or '-1')
                    except ValueError:
                        continue
                    if 0 <= index <= 8 and 0 < value < 100000:
                        overrides[index] = value
                self.concrete[num_id] = abstract_id,overrides
            # Only infer a style's numbering when its abstract list maps to a
            # unique concrete numId. Repeated/restarted list IDs are ambiguous.
            style_choices = {}
            for num_id,(abstract_id,_overrides) in self.concrete.items():
                for style_id,level in self.abstract_styles.get(abstract_id,{}).items():
                    style_choices.setdefault(style_id,[]).append((num_id,level))
            self.linked_styles = {style:vals[0] for style,vals in style_choices.items()
                                  if len(vals)==1}

    def _val(self, parent: ET.Element | None, tag: str) -> str | None:
        if parent is None:
            return None
        node = parent.find(self.w(tag))
        return node.get(self.w('val')) if node is not None else None

    def _style_number(self, style_id: str | None) -> tuple[str | None,str | None]:
        for _ in range(16):
            if not style_id or style_id not in self.style_defs:
                break
            based, num_id, ilvl = self.style_defs[style_id]
            if num_id is not None:
                return num_id, ilvl
            if style_id in self.linked_styles:
                linked_id,level=self.linked_styles[style_id]
                return linked_id,str(level)
            style_id = based
        return None, None

    def paragraph_info(self, paragraph: ET.Element) -> dict:
        ppr = paragraph.find(self.w('pPr'))
        style = self._val(ppr,'pStyle')
        num_pr = ppr.find(self.w('numPr')) if ppr is not None else None
        num_id, level_raw = self._val(num_pr,'numId'), self._val(num_pr,'ilvl')
        if num_id is None:
            num_id, style_level = self._style_number(style)
            level_raw = level_raw if level_raw is not None else style_level
        elif level_raw is None:
            style_num_id, style_level = self._style_number(style)
            if style_num_id == num_id:
                level_raw=style_level
        result={'style':style or '', 'numbering_label':'', 'numbering_status':'none'}
        if num_id is None or num_id == '0':
            return result
        self.numbered_paragraphs += 1
        result['numbering_status'] = 'unresolved'
        entry = self.concrete.get(num_id)
        try:
            level = int(level_raw or '0')
        except ValueError:
            level = -1
        if entry is None or level < 0 or level > 8:
            self.unresolved_numbered_paragraphs += 1
            return result
        abstract_id, overrides = entry
        level_def = self.abstract.get(abstract_id,{}).get(level)
        if level_def is None:
            self.unresolved_numbered_paragraphs += 1
            return result
        start, fmt, template = level_def
        counter = self.counters.setdefault(num_id,{})
        counter[level] = counter.get(level, overrides.get(level,start)-1)+1
        for k in list(counter):
            if k > level:
                del counter[k]
        references = [int(x)-1 for x in re.findall(r'%([1-9])',template)]
        if fmt != 'decimal' or not references or any(k not in counter for k in references):
            self.unresolved_numbered_paragraphs += 1
            return result
        label = re.sub(r'%([1-9])',lambda m:str(counter[int(m.group(1))-1]),template)
        # Only return true decimal-based numbering, not symbols or bullets.
        if not re.fullmatch(r'\d+(?:[.\-]\d+){0,5}[.]?',label):
            self.unresolved_numbered_paragraphs += 1
            return result
        result['numbering_label']=label.rstrip('.')
        result['numbering_status']='resolved'
        return result
