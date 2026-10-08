from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from noark5_workflow.operations.dias_mets import (
    METS_NS,
    SUBMISSION_DESCRIPTION_XSD,
    build_dias_mets_metadata,
    build_submission_description,
    read_meta_from_mets,
    write_xml,
)


def _values() -> dict[str, str]:
    return {
        "archive_description": "1502_024 ePhorte mk (2005-2007)",
        "submission_agreement": "18/690-2; 2018-10-09",
        "record_status": "NEW",
        "delivery_type": "Sak-/Arkivsystem",
        "project_name": "Depotmottak",
        "package_number": "1.0",
        "reference_code": "1502_024",
        "archivist_org": "1502 Molde kommune",
        "archivist_person": "Arkivleder",
        "archivist_address": "Rådhusplassen 1",
        "archivist_phone": "70110000",
        "archivist_email": "arkiv@example.no",
        "submitter_org": "IKAMR",
        "submitter_person": "Innleverer",
        "submitter_email": "inn@example.no",
        "producer_org": "Leverandør AS",
        "producer_person": "Uttrekksansvarlig",
        "producer_phone": "99999999",
        "owner_org": "1502 Molde kommune",
        "owner_person": "Arkivleder",
        "creator_org": "IKAMR",
        "creator_person": "Metadataansvarlig",
        "recipient": "Interkommunalt Arkiv for Møre og Romsdal IKS",
        "system": "ePhorte",
        "system_version": "4.2",
        "system_type": "Noark5",
        "system_type_version": "5.0",
        "extraction_system": "Documaster",
        "extraction_system_version": "1.2.3",
        "extraction_system_type": "Noark5",
        "extraction_system_type_version": "5.0",
        "period_start": "02.05.2005",
        "period_end": "31.12.2007",
        "extraction_date": "2026-10-08",
        "label": "1502_024 ePhorte mk (2005-2007)",
    }


class V017A2DiasMetadataTests(unittest.TestCase):
    def test_submission_description_matches_arkade_mapping_and_roundtrips(self):
        values = _values()
        tree = build_submission_description(
            values,
            object_id="UUID:11111111-2222-3333-4444-555555555555",
            created_at="2026-10-08T10:00:00+02:00",
            software_name="Data Workflow Manager",
            software_version="0.1.7-a2",
        )
        root = tree.getroot()
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        self.assertEqual(root.get("TYPE"), "SIP")
        self.assertEqual(root.get("PROFILE"), "http://xml.ra.se/METS/RA_METS_eARD.xml")
        self.assertIn(SUBMISSION_DESCRIPTION_XSD, root.get(f"{{{xsi}}}schemaLocation", ""))
        self.assertEqual(root.get("LABEL"), values["label"])

        hdr = root.find(f"{{{METS_NS}}}metsHdr")
        self.assertIsNotNone(hdr)
        self.assertEqual(hdr.get("RECORDSTATUS"), "NEW")
        alts = {
            node.get("TYPE"): (node.text or "")
            for node in hdr.findall(f"{{{METS_NS}}}altRecordID")
        }
        self.assertEqual(alts["DELIVERYSPECIFICATION"], values["archive_description"])
        self.assertEqual(alts["SUBMISSIONAGREEMENT"], values["submission_agreement"])
        self.assertEqual(alts["DELIVERYTYPE"], values["delivery_type"])
        self.assertEqual(alts["PACKAGENUMBER"], values["package_number"])
        self.assertEqual(alts["REFERENCECODE"], values["reference_code"])
        self.assertEqual(alts["STARTDATE"], "2005-05-02")
        self.assertEqual(alts["ENDDATE"], "2007-12-31")
        # Arkade 5 SubmissionDescriptionCreator does not currently materialize
        # PROJECTNAME even though the shared metadata model contains it.
        self.assertNotIn("PROJECTNAME", alts)

        with tempfile.TemporaryDirectory() as tmp:
            target = write_xml(tree, Path(tmp) / "info.xml")
            parsed = read_meta_from_mets(target)
        for key in (
            "archive_description", "submission_agreement", "record_status",
            "delivery_type", "package_number", "reference_code", "label",
            "archivist_org", "archivist_person", "archivist_address",
            "archivist_phone", "archivist_email", "submitter_org",
            "producer_org", "owner_org", "creator_org", "recipient",
            "system", "system_version", "system_type", "system_type_version",
            "extraction_system", "extraction_system_version",
            "extraction_system_type", "extraction_system_type_version",
        ):
            self.assertEqual(parsed.get(key), values[key], key)

    def test_inner_dias_mets_uses_same_metadata_and_keeps_project_name(self):
        values = _values()
        tree = build_dias_mets_metadata(
            values,
            object_id="UUID:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            created_at="2026-10-08T10:00:00+02:00",
            software_name="Data Workflow Manager",
            software_version="0.1.7-a2",
        )
        root = tree.getroot()
        hdr = root.find(f"{{{METS_NS}}}metsHdr")
        alts = {
            node.get("TYPE"): (node.text or "")
            for node in hdr.findall(f"{{{METS_NS}}}altRecordID")
        }
        self.assertEqual(alts["PROJECTNAME"], values["project_name"])
        document_id = hdr.find(f"{{{METS_NS}}}metsDocumentID")
        self.assertEqual((document_id.text or ""), "dias-mets.xml")
        # Extraction date is stored in DWM, but its inner-METS XML mapping is
        # not yet agreed and must not be invented by the shell builder.
        self.assertIsNone(root.find(f"{{{METS_NS}}}fileSec"))

    def test_typeversion_only_for_noark5_output(self):
        values = _values()
        values["system_type"] = "SIARD"
        values["system_type_version"] = "5.0"
        values["extraction_system_type"] = "Noark 5"
        root = build_submission_description(values).getroot()
        agents = root.findall(f"{{{METS_NS}}}metsHdr/{{{METS_NS}}}agent")
        system = next(a for a in agents if a.get("ROLE") == "ARCHIVIST" and a.get("OTHERTYPE") == "SOFTWARE")
        extraction = next(a for a in agents if a.get("OTHERROLE") == "PRODUCER" and a.get("OTHERTYPE") == "SOFTWARE")
        notes = lambda agent: [(n.text or "") for n in agent.findall(f"{{{METS_NS}}}note")]
        self.assertEqual(notes(system), ["4.2", "SIARD", "notescontent:Version,Type"])
        self.assertEqual(notes(extraction), ["1.2.3", "Noark 5", "5.0", "notescontent:Version,Type,TypeVersion"])

    def test_arkade_notescontent_is_parsed_for_contact_and_system_fields(self):
        xml = '''<?xml version="1.0" encoding="utf-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Test" TYPE="SIP"
 PROFILE="http://xml.ra.se/METS/RA_METS_eARD.xml" OBJID="UUID:test">
  <mets:metsHdr CREATEDATE="2026-10-08T10:00:00+02:00" RECORDSTATUS="NEW">
    <mets:agent ROLE="ARCHIVIST" TYPE="ORGANIZATION"><mets:name>Kommune</mets:name></mets:agent>
    <mets:agent ROLE="ARCHIVIST" TYPE="INDIVIDUAL"><mets:name>Arkivleder</mets:name>
      <mets:note>Gate 1</mets:note><mets:note>70110000</mets:note><mets:note>a@example.no</mets:note>
      <mets:note>notescontent:Address,Telephone,Email</mets:note>
    </mets:agent>
    <mets:agent ROLE="CREATOR" TYPE="OTHER" OTHERTYPE="SOFTWARE"><mets:name>Arkade 5</mets:name>
      <mets:note>2.13.1</mets:note><mets:note>notescontent:Version</mets:note>
    </mets:agent>
    <mets:agent ROLE="ARCHIVIST" TYPE="OTHER" OTHERTYPE="SOFTWARE"><mets:name>ePhorte</mets:name>
      <mets:note>4.2</mets:note><mets:note>Noark5</mets:note><mets:note>5.0</mets:note>
      <mets:note>notescontent:Version,Type,TypeVersion</mets:note>
    </mets:agent>
    <mets:altRecordID TYPE="SUBMISSIONAGREEMENT">18/690</mets:altRecordID>
  </mets:metsHdr><mets:structMap><mets:div/></mets:structMap>
</mets:mets>'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "info.xml"
            path.write_text(xml, encoding="utf-8")
            parsed = read_meta_from_mets(path)
        self.assertEqual(parsed["archivist_address"], "Gate 1")
        self.assertEqual(parsed["archivist_phone"], "70110000")
        self.assertEqual(parsed["archivist_email"], "a@example.no")
        self.assertEqual(parsed["mets_creator_software"], "Arkade 5")
        self.assertEqual(parsed["mets_creator_software_version"], "2.13.1")
        self.assertEqual(parsed["system"], "ePhorte")
        self.assertEqual(parsed["system_version"], "4.2")
        self.assertEqual(parsed["system_type"], "Noark5")
        self.assertEqual(parsed["system_type_version"], "5.0")

    def test_legacy_dwm_split_system_agents_remain_readable(self):
        xml = """<?xml version="1.0" encoding="utf-8"?>
<mets:mets xmlns:mets="http://www.loc.gov/METS/" LABEL="Testpakke">
  <mets:metsHdr>
    <mets:agent TYPE="OTHER" OTHERTYPE="SOFTWARE" ROLE="ARCHIVIST"><mets:name>Kildesystem</mets:name></mets:agent>
    <mets:agent TYPE="OTHER" OTHERTYPE="SOFTWARE" ROLE="ARCHIVIST"><mets:name>2.3</mets:name></mets:agent>
    <mets:agent TYPE="OTHER" OTHERTYPE="SOFTWARE" ROLE="ARCHIVIST"><mets:name>NOARK-5</mets:name></mets:agent>
  </mets:metsHdr>
</mets:mets>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.xml"
            path.write_text(xml, encoding="utf-8")
            parsed = read_meta_from_mets(path)
        self.assertEqual(parsed["system"], "Kildesystem")
        self.assertEqual(parsed["system_version"], "2.3")
        self.assertEqual(parsed["system_type"], "NOARK-5")
        self.assertEqual(parsed["archivist_type"], "NOARK-5")

    def test_editor_keeps_spreadsheet_order_and_normal_work_window(self):
        source = Path(__file__).resolve().parents[1] / "gui" / "depot_metadata_editor_v017_a1.py"
        text = source.read_text(encoding="utf-8")
        expected = [
            '"archive_description", "Arkivbeskrivelse"',
            '"submission_agreement", "Avtalenr"',
            '"record_status", "Oppføringstype"',
            '"delivery_type", "Arkivsystemtype"',
            '"archivist_org", "Arkivskaper"',
            '"submitter_org", "Overfører"',
            '"producer_org", "Produsent"',
            '"owner_org", "Eier"',
            '"creator_org", "Skaper info.xml"',
            '"mets_creator_software", "METS program"',
            '"recipient", "Mottaker"',
            '"system", "Systemnavn"',
            '"extraction_system", "Uttrekkssystem"',
            '"period_start", "Startdato"',
            '"period_end", "Sluttdato"',
            '"extraction_date", "Uttrekksdato"',
            '"label", "Merkelapp"',
        ]
        positions = [text.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('self.geometry("1120x820")', text)
        self.assertIn('self.resizable(True, True)', text)
        self.assertNotIn('self.transient(master)', text)


if __name__ == "__main__":
    unittest.main()
