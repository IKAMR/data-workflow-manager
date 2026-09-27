from __future__ import annotations

import json
from pathlib import Path

from noark5_workflow.analysis import defined_fields


def _definition(path: Path) -> None:
    document = {
        "format_version": 1,
        "definition_id": "noark5.archive_structure.metadata.v1",
        "source": "arkivstruktur.xml",
        "entities": {
            "archive": {
                "scope": "single",
                "select": "//*[local-name()='arkiv']",
                "fields": {},
                "children": {"creators": {"select": ".//*[local-name()='arkivskaper']", "fields": {}}},
            },
            "archive_parts": {
                "scope": "many",
                "select": "//*[local-name()='arkivdel']",
                "fields": {},
            },
        },
    }
    path.write_text(json.dumps(document), encoding="utf-8")


def test_default_defined_fields_uses_streaming_not_lxml_xpath(tmp_path, monkeypatch):
    xml = tmp_path / "arkivstruktur.xml"
    xml.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<n5:arkiv xmlns:n5='urn:noark5'>
  <n5:systemID>A-1</n5:systemID>
  <n5:tittel>Hovedarkiv</n5:tittel>
  <n5:arkivstatus>O</n5:arkivstatus>
  <n5:arkivskaper>
    <n5:arkivskaperNavn>IKAMR</n5:arkivskaperNavn>
    <n5:arkivskaperID>123</n5:arkivskaperID>
    <n5:beskrivelse>Skaper</n5:beskrivelse>
  </n5:arkivskaper>
  <n5:arkivdel>
    <n5:tittel>Del 1</n5:tittel>
    <n5:beskrivelse>Arkivdeltekst</n5:beskrivelse>
    <n5:arkivdelstatus>A</n5:arkivdelstatus>
    <n5:mappe><n5:tittel>Skal ikke overskrive arkivtittel</n5:tittel></n5:mappe>
  </n5:arkivdel>
  <n5:arkivdel>
    <n5:tittel>Del 2</n5:tittel>
    <n5:arkivdelstatus>P</n5:arkivdelstatus>
  </n5:arkivdel>
</n5:arkiv>
""",
        encoding="utf-8",
    )
    definition = tmp_path / "fields.json"
    _definition(definition)

    def forbidden_parse(*_args, **_kwargs):
        raise AssertionError("lxml etree.parse must not run for the default definition")

    monkeypatch.setattr(defined_fields.etree, "parse", forbidden_parse)

    result = defined_fields.extract_defined_fields(xml, definition)

    assert result["archive_count"] == 1
    assert result["archive"]["system_id"] == "A-1"
    assert result["archive"]["title"] == "Hovedarkiv"
    assert result["archive"]["status"] == "O"
    assert result["archive"]["creators"] == [
        {
            "name": "IKAMR",
            "id": "123",
            "description": "Skaper",
            "index": 1,
        }
    ]
    assert result["archive_parts_count"] == 2
    assert result["archive_parts"][0]["title"] == "Del 1"
    assert result["archive_parts"][0]["description"] == "Arkivdeltekst"
    assert result["archive_parts"][1]["title"] == "Del 2"
