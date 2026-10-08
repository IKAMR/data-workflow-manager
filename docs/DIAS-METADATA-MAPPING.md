# DIAS metadata mapping

Data Workflow Manager keeps one canonical metadata model for the DIAS package.
The field order follows rows 1-47 in IKAMR's `0000-metadata-arkade.xlsx` and the
Arkade 5 metadata GUI / `ArchiveMetadata` model.

The same values are materialized in two related METS documents:

- **Outer package submission description** (commonly `info.xml` or a UUID XML
  beside the package): structure from Arkade 5 `SubmissionDescriptionCreator`,
  `submissionDescription.xsd`.
- **Inner package METS** (`dias-mets.xml` inside the SIP/AIP): structure from
  Arkade 5 `DiasMetsCreator`, `DIAS_METS.xsd`.

These documents intentionally overlap heavily but are not identical. DWM must
never collapse them into one format.

| # | UI field | Canonical key | Outer submission description | Inner dias-mets.xml |
|---:|---|---|---|---|
| 1 | Arkivbeskrivelse | `archive_description` | `altRecordID@TYPE=DELIVERYSPECIFICATION` | same |
| 2 | Avtalenr | `submission_agreement` | `SUBMISSIONAGREEMENT` | same |
| 3 | Oppføringstype | `record_status` | `metsHdr/@RECORDSTATUS` | same |
| 4 | Arkivsystemtype | `delivery_type` | `DELIVERYTYPE` | same |
| 5 | Prosjektnavn | `project_name` | not emitted by current Arkade 5 SubmissionDescriptionCreator | `PROJECTNAME` |
| 6 | Pakkenummer | `package_number` | `PACKAGENUMBER` | same |
| 7 | Referansekode | `reference_code` | `REFERENCECODE` | same |
| 8-12 | Arkivskaper + kontakt | `archivist_*` | `agent ROLE=ARCHIVIST` organization/individual + notes | same |
| 13-17 | Overfører + kontakt | `submitter_*` | `agent ROLE=OTHER OTHERROLE=SUBMITTER` | same |
| 18-22 | Produsent + kontakt | `producer_*` | `agent ROLE=OTHER OTHERROLE=PRODUCER` | same |
| 23-27 | Eier + kontakt | `owner_*` | `agent ROLE=IPOWNER` | same |
| 28-32 | Skaper info.xml + kontakt | `creator_*` | `agent ROLE=CREATOR` organization/individual | same |
| 33-34 | METS program + versjon | `mets_creator_software*` | `agent ROLE=CREATOR TYPE=OTHER OTHERTYPE=SOFTWARE` | same |
| 35 | Mottaker | `recipient` | `agent ROLE=PRESERVATION TYPE=ORGANIZATION` | same |
| 36-39 | Systemnavn / versjon / type / typeversjon | `system*` | `agent ROLE=ARCHIVIST TYPE=OTHER OTHERTYPE=SOFTWARE` + Arkade notes | same |
| 40-43 | Uttrekkssystem / versjon / type / typeversjon | `extraction_system*` | `agent ROLE=OTHER OTHERROLE=PRODUCER TYPE=OTHER OTHERTYPE=SOFTWARE` + Arkade notes | same |
| 44 | Startdato | `period_start` | `STARTDATE` | same |
| 45 | Sluttdato | `period_end` | `ENDDATE` | same |
| 46 | Uttrekksdato | `extraction_date` | No approved XML mapping | Mapping pending; stored in DWM only for now |
| 47 | Merkelapp | `label` | `mets/@LABEL` | same |

## Arkade 5 note convention

METS itself permits repeated `<mets:note>` without assigning predefined meaning
or labels to each note. Arkade 5 encodes contact/system subfields as ordered
`<mets:note>` values and uses the **last note** as an explicit
`notescontent:` marker identifying which of the earlier notes mean what.

Example for an `INDIVIDUAL` contact agent belonging to an organization:

```xml
<mets:note>Gate 1</mets:note>
<mets:note>70110000</mets:note>
<mets:note>arkiv@example.no</mets:note>
<mets:note>notescontent:Address,Telephone,Email</mets:note>
```

The marker is Arkade 5's interpretation convention, not a generic METS
requirement. The same principle is used for software agents:

```xml
<mets:note>4.2</mets:note>
<mets:note>Noark5</mets:note>
<mets:note>5.0</mets:note>
<mets:note>notescontent:Version,Type,TypeVersion</mets:note>
```

DWM reads and writes this convention for outer and inner METS. The agent's
`name` contains the person or software name; it is **not** a `note`.

## System and extraction software

For both `system*` and `extraction_system*`, `Name` is the software/system name,
`Version` is its software version, and `Type` is the extraction format (for
example Noark 5 or SIARD). `TypeVersion` is only meaningful for Noark 5, with
values 3.1, 4.0 or 5.0. For other formats, it is omitted from generated METS.
Historical imported values must not be silently deleted from source evidence.

## Recipient and extraction date

`recipient` is the **recipient organization** (`PRESERVATION / ORGANIZATION`),
not the logged-in individual user. The organization must be configurable per
deployment, rather than hardcoded to IKAMR. Do not replace an imported value
with a user's personal name. A missing or disputed depot organization must be
resolved explicitly, not guessed from the current user.

`extraction_date` is an independently persisted and editable depot value.
The outer `info.xml` does not currently map it. Its mapping in inner
`dias-mets.xml` requires a separate decision; DWM must not export a speculative
`ArchiveExtraction/@VERSDATE` from this field until agreed.

Imported XML is retained unchanged as source evidence. Corrected/current depot
metadata is stored separately. Original METS software provenance and a newly
DWM-generated document's software creator are distinct facts.

Rows 48 and onward in the IKAMR spreadsheet are depot/process/SIARD/package
tracking data and are not treated as DIAS METS metadata.
