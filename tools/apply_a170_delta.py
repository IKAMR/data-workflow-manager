"""Apply the a170-180 delta on a clean v0.2.4-a2 repository copy.

Run from repo root: py tools/apply_a170_delta.py
No Work files, .n5jobs or source extraction are ever touched.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str):
    target = ROOT / path
    raw = target.read_text(encoding='utf-8')
    if new in raw:
        print('already patched:', path)
        return
    n = raw.count(old)
    if n != 1:
        raise RuntimeError(f'Expected one unchanged a2 anchor in {path}, got {n}: {old[:70]!r}')
    target.write_text(raw.replace(old, new, 1), encoding='utf-8')
    print('patched:', path)


def main():
    # Verify source version and all anchor strings BEFORE changing any file.
    version = (ROOT / 'version.py').read_text(encoding='utf-8')
    if 'VERSION = "0.2.4-a2"' not in version:
        raise RuntimeError('This delta requires the v0.2.4-a2 base. Do not apply to laptop a3.')
    cfg_path = ROOT / 'config/noark5/arkivstruktur_fields.json'
    config = json.loads(cfg_path.read_text(encoding='utf-8'))
    part = config['entities']['archive_parts']
    if 'ancestor_fields' not in part:
        part['ancestor_fields'] = {
            'parent_archive_system_id': {'entity': 'archive', 'field': 'system_id'},
            'parent_archive_title': {'entity': 'archive', 'field': 'title'},
        }
        # A170 included system_id as an archive-part field.
        if 'system_id' not in part['fields']:
            part['fields'] = {'system_id': "string(./*[local-name()='systemID'][1])", **part['fields']}
        cfg_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('patched:', cfg_path.relative_to(ROOT))

    p = 'noark5_workflow/analysis/defined_fields.py'
    replace_once(p,
        '        plan[str(entity_id)] = {\n            "tag": entity_tag,',
        '''        ancestor_fields = entity.get("ancestor_fields", {})
        if not isinstance(ancestor_fields, dict):
            return None
        for relation in ancestor_fields.values():
            if not isinstance(relation, dict) or not relation.get("entity") or not relation.get("field"):
                return None
        plan[str(entity_id)] = {
            "ancestor_fields": ancestor_fields,
            "tag": entity_tag,''')
    replace_once(p,
        '''                            "values": {},
                            "children": {
                                child_id: []
                                for child_id in entity_plan["children"]
                            },''',
        '''                            "values": {},
                            "ancestor_owners": {
                                owner_id: entity_stacks[owner_id][-1]
                                if owner_id in entity_stacks and entity_stacks[owner_id]
                                else None
                                for owner_id in {
                                    str(rel["entity"])
                                    for rel in entity_plan["ancestor_fields"].values()
                                }
                            },
                            "children": {
                                child_id: []
                                for child_id in entity_plan["children"]
                            },''')
    replace_once(p,
        '''                    values["index"] = len(extracted[entity_id]) + 1
                    for child_id, items in state["children"].items():''',
        '''                    values["index"] = len(extracted[entity_id]) + 1
                    if entity_plan["ancestor_fields"]:
                        values["_ancestor_owners"] = state["ancestor_owners"]
                    for child_id, items in state["children"].items():''')
    replace_once(p,
        '''    result: dict[str, Any] = {
        "definition_id": definition["definition_id"],
        "source": str(xml_path.resolve()),
    }
    for entity_id, entity_plan in plan.items():
        rows = extracted[entity_id]''',
        '''    # Owners are retained as dict references, so relation resolution also
    # works when archive metadata follows an archive part in document order.
    for entity_id, entity_plan in plan.items():
        for row in extracted[entity_id]:
            owners = row.pop("_ancestor_owners", {})
            for field_id, rel in entity_plan["ancestor_fields"].items():
                owner = owners.get(str(rel["entity"]))
                row[field_id] = owner["values"].get(str(rel["field"]), "") if owner else ""

    result: dict[str, Any] = {
        "definition_id": definition["definition_id"],
        "source": str(xml_path.resolve()),
    }
    for entity_id, entity_plan in plan.items():
        rows = extracted[entity_id]''')

    replace_once('noark5_workflow/operations/analyse_noark5_core.py',
        '''from noark5_workflow.analysis.definition_engine import (
    AnalysisDefinitionError,
    run_definition_analysis,
    write_analysis_result,
)''',
        '''from noark5_workflow.analysis.definition_engine import (
    AnalysisDefinitionError,
    write_analysis_result,
)
from noark5_workflow.analysis.legacy_a170_stream import run_legacy_a170_stream''')
    replace_once('noark5_workflow/operations/analyse_noark5_core.py',
        '            result = run_definition_analysis(arkivstruktur, DEFINITION_PATH)',
        '            result = run_legacy_a170_stream(arkivstruktur, DEFINITION_PATH)')
    replace_once('noark5_workflow/operations/analyse_noark5_core.py',
        '        except (OSError, etree.XMLSyntaxError, AnalysisDefinitionError, ValueError) as exc:',
        '        except (OSError, etree.XMLSyntaxError, etree.XPathError, AnalysisDefinitionError, ValueError) as exc:')
    replace_once('noark5_workflow/operations/analyse_noark5_u1.py',
        '        name="Noark 5 U1 – samlet opptelling",',
        '        name="Noark 5 U1 – samlet opptelling (Legacy)",')
    replace_once('noark5_workflow/operations/analyse_noark5_core.py',
        '        name="Noark 5-analyse: arkiv og arkivdel",',
        '        name="Noark 5-analyse: arkiv og arkivdel (Legacy)",')
    replace_once('noark5_workflow/core/job_runner.py',
        '''            all_ok = True
            for zero_index in range(start_index, total):''',
        '''            all_ok = True
            current_index = start_index
            for zero_index in range(start_index, total):
                current_index = zero_index''')
    replace_once('noark5_workflow/core/job_runner.py',
        '''        except Exception as exc:
            job.status = JobStatus.FAILED
            job.message = (
                f"Fortsettelse feilet - prøv igjen fra operasjon {start_index + 1}"
                if resuming else str(exc)
            )''',
        '''        except Exception as exc:
            job.status = JobStatus.FAILED
            # Exception may happen AFTER a previously resumed operation succeeded.
            # Record the actual failed operation, not the original start cursor.
            failed_index = locals().get("current_index", start_index)
            job.next_operation_index = failed_index
            job.progress = failed_index / len(op_ids)
            job.message = (
                f"Fortsettelse feilet - prøv igjen fra operasjon {failed_index + 1}"
                if resuming else str(exc)
            )''')
    print('Delta applied. Run: py -m unittest tests.test_a170_legacy_delta -v')


if __name__ == '__main__':
    main()
