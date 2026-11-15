"""A8 read-only five-XML technical XSD validation, per explicit Noark version.

Four Noark 5 XSDs cover archive structure, change log and the two journals.
metadatakatalog.xsd is a shared schema dependency, not a fifth export XML.
arkivuttrekk.xml needs the supplied ADDML schema when present; do not pretend
metadatakatalog.xsd validates it.  Missing optional files are NOT failures of
normative compliance.  This never modifies XML or source schemas.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from lxml import etree
from app.noark_xsd_variant_qa_v021_a5 import _schema_dependencies

XML_TO_SCHEMA = {
    'arkivstruktur.xml':'arkivstruktur.xsd',
    'endringslogg.xml':'endringslogg.xsd',
    'loependeJournal.xml':'loependeJournal.xsd',
    'offentligJournal.xml':'offentligJournal.xsd',
    'arkivuttrekk.xml':None,  # ADDML.xsd, not metadatakatalog.xsd
}
VERSIONS=('3.1','4.0','5.0')
MAX_XML_BYTES=256_000_000
MAX_ERROR_SAMPLES=250
MAX_SCHEMA_BYTES=5_000_000


def _safe_child(root: Path, name: str) -> Path:
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Filsti peker ut av valgt rot: '+name)
    return path


def _manifest(source_root: Path) -> dict[str,dict]:
    path=source_root/'docs/kilder/noark/SOURCE-MANIFEST.json'
    if not path.is_file() or path.stat().st_size>5_000_000:
        raise ValueError('Kildemanifest mangler eller er for stort')
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict) or not isinstance(obj.get('files'),list):
        raise ValueError('Ugyldig kildemanifest')
    return {item['path']:item for item in obj['files']
            if isinstance(item,dict) and isinstance(item.get('path'),str)}



def _dwm_signatures(registry_path: Path | str | None = None) -> dict[tuple[str,str],str]:
    """Independent DWM pins; a changed source manifest cannot redefine originals."""
    path=(Path(registry_path) if registry_path else
          Path(__file__).resolve().parents[1]/'config/noark5/standards/noark5_xsd_signatures_v0114_a5.json')
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError('Fastlagt DWM XSD-signaturregister mangler')
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict) or not isinstance(obj.get('signatures'),list):
        raise ValueError('Ugyldig DWM XSD-signaturregister')
    result={}
    for item in obj['signatures']:
        if not isinstance(item,dict):
            continue
        key=(item.get('version'),item.get('filename'))
        digest=item.get('sha256')
        if not (isinstance(digest,str) and len(digest)==64):
            raise ValueError('Ugyldig DWM XSD-signatur')
        if key in result:
            raise ValueError('Duplikat XSD-signatur i DWM-register')
        result[key]=digest
    return result


def _schema_path(source:Path, version:str, name:str, manifest:dict,
                 signatures:dict) -> tuple[Path|None,str]:
    relative=f'noark5/v{version}/schemas/{name}'
    item=manifest.get(relative)
    if not item or not isinstance(item.get('sha256'),str):
        return None,'manifest_entry_missing'
    expected=signatures.get((version,name))
    if expected is None:
        return None,'dwm_signature_entry_missing'
    if expected != item['sha256']:
        return None,'dwm_xsd_signature_mismatch'
    path=_safe_child(source/'docs/kilder/noark',relative)
    if not path.is_file() or path.stat().st_size>MAX_SCHEMA_BYTES:
        return None,'schema_file_missing_or_too_large'
    if sha256(path.read_bytes()).hexdigest()!=item['sha256']:
        return None,'schema_source_sha256_mismatch'
    return path,'original_sha256_verified'


def _xmlschema(path:Path):
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False)
    parsed=etree.parse(str(path),parser)
    return etree.XMLSchema(parsed)


def validate_extraction(extraction_root:Path|str, source_root:Path|str,
                        *, noark_version:str, max_xml_bytes:int=MAX_XML_BYTES,
                        signature_registry:Path|str|None=None) -> dict[str,Any]:
    if noark_version not in VERSIONS:
        raise ValueError('Velg eksakt Noark 5-versjon: 3.1, 4.0 eller 5.0')
    if not 1<=max_xml_bytes<=MAX_XML_BYTES:
        raise ValueError('Ugyldig XML-størrelsesgrense')
    extraction=Path(extraction_root).resolve(strict=True)
    source=Path(source_root).resolve(strict=True)
    if not extraction.is_dir() or not source.is_dir() or extraction==source or extraction.is_relative_to(source) or source.is_relative_to(extraction):
        raise ValueError('Kildekatalog og uttrekkskatalog må være separate')
    manifest=_manifest(source)
    signatures=_dwm_signatures(signature_registry)
    # Shared metadatakatalog.xsd is checked independently even when no XML
    # references it, and any corruption blocks a normative XSD verdict.
    inventory={}
    for name in ('arkivstruktur.xsd','metadatakatalog.xsd','endringslogg.xsd',
                 'loependeJournal.xsd','offentligJournal.xsd'):
        path,status=_schema_path(source,noark_version,name,manifest,signatures)
        inventory[name]={'status':status,'source':str(path) if path else None,
                         'dwm_pinned_sha256':signatures.get((noark_version,name)),
                         'source_sha256':sha256(path.read_bytes()).hexdigest() if path else None}
    records=[]
    for xml_name, schema_name in XML_TO_SCHEMA.items():
        path=_safe_child(extraction,xml_name)
        record={'xml_file':xml_name,'schema_file':schema_name,
                'technical_xsd_status':'NOT_RUN','qa_severity':'NOTE',
                'schema_original_sha256_verified':False,
                'normative_conformance_verified':False,
                'error_count':0,'error_samples':[]}
        if not path.is_file():
            record['technical_xsd_status']='XML_FILE_NOT_PRESENT'
            record['note']='Filens obligatoriske forekomst er ikke avgjort av denne kontrollen.'
            records.append(record)
            continue
        if path.stat().st_size>max_xml_bytes:
            record['technical_xsd_status']='SKIPPED_LARGE_XML'
            record['note']='XML-filen overstiger ressursgrensen; ingen bestått-stempel.'
            record['qa_severity']='WARNING'
            records.append(record)
            continue
        if schema_name:
            info=inventory[schema_name]
            schema=Path(info['source']) if info['source'] else None
            record['schema_original_sha256_verified']=info['status']=='original_sha256_verified'
            if not schema:
                record['technical_xsd_status']='SCHEMA_SOURCE_UNAVAILABLE'
                record['qa_severity']='FEIL'
                records.append(record)
                continue
        else:
            # This is a separately supplied ADDML schema, not a Noark 5
            # normative schema in our 15-XSD source set.
            schema=_safe_child(extraction,'addml.xsd')
            if not schema.is_file():
                record['technical_xsd_status']='ADDML_SCHEMA_NOT_PRESENT'
                record['qa_severity']='WARNING'
                record['note']='arkivuttrekk.xml kan ikke testes uten medfølgende ADDML XSD.'
                records.append(record)
                continue
            if schema.stat().st_size>MAX_SCHEMA_BYTES:
                record['technical_xsd_status']='ADDML_SCHEMA_TOO_LARGE'
                record['qa_severity']='WARNING'
                records.append(record)
                continue
            record['schema_file']='addml.xsd (supplied in extract)'
            record['addml_schema_sha256']=sha256(schema.read_bytes()).hexdigest()
            record['schema_original_sha256_verified']=False
        try:
            dependencies = _schema_dependencies(schema)
            record['schema_dependency_sha256'] = dependencies
            if schema_name:
                if any(name not in inventory or inventory[name]['source_sha256'] != digest
                       or inventory[name]['status'] != 'original_sha256_verified'
                       for name,digest in dependencies.items()):
                    record['technical_xsd_status']='SCHEMA_DEPENDENCY_UNVERIFIED'
                    record['qa_severity']='FEIL'
                    record['note']='XSD-avhengighet mangler i det SHA-verifiserte kildegrunnlaget.'
                    records.append(record)
                    continue
            xml_parser=etree.XMLParser(resolve_entities=False,no_network=True,
                                       load_dtd=False,huge_tree=True)
            xml_doc=etree.parse(str(path),xml_parser)
            compiled=_xmlschema(schema)
            valid=compiled.validate(xml_doc)
            record['technical_xsd_status']='XSD_VALID' if valid else 'XSD_INVALID'
            record['qa_severity']='NOTE' if valid else 'FEIL'
            record['error_count']=len(compiled.error_log)
            record['error_samples']=[{'line':x.line,'column':x.column,
                     'domain':x.domain_name,'type':x.type_name,
                     'path':x.path,'message':x.message[:500]}
                     for x in list(compiled.error_log)[:MAX_ERROR_SAMPLES]]
            if valid and not schema_name:
                record['note']='Gyldighet mot medfølgende ADDML-skjema; schemaoriginalitet ikke attestert.'
        except (etree.XMLSyntaxError, etree.XMLSchemaParseError, etree.XMLSchemaError,
                OSError,ValueError) as exc:
            record['technical_xsd_status']='XSD_CHECK_ERROR'
            record['qa_severity']='FEIL'
            record['note']=f'{type(exc).__name__}: {str(exc)[:450]}'
        records.append(record)
    return {
        'report_format_version':1,
        'report_type':'noark5_a8_five_xml_technical_xsd_not_normative_conformance',
        'noark_version':noark_version,
        'schema_source_repository':'IKAMR/digital-archive-workflow',
        'dwm_pinned_signatures_required':True,
        'original_xsd_inventory':inventory,
        'xml_records':records,
        'technical_status_counts':{s:sum(x['technical_xsd_status']==s for x in records)
                                   for s in sorted({x['technical_xsd_status'] for x in records})},
        'source_files_modified':False,'original_xml_files_modified':False,
        'full_noark_conformance_verified':False,
        'schema_validation_not_semantic_requirement_review':True,
        'note':'5 XML-filer: fire normative Noark-XSDer og arkivuttrekk.xml mot separat ADDML. Manglende XML er ikke automatisk avvik.',
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extraction-root',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--noark-version',required=True,choices=VERSIONS)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-xml-bytes',type=int,default=MAX_XML_BYTES)
    args=parser.parse_args(argv)
    try:
        report=validate_extraction(args.extraction_root,args.source_root,
                                  noark_version=args.noark_version,
                                  max_xml_bytes=args.max_xml_bytes)
        output=args.output.resolve()
        for forbidden in (args.extraction_root,args.source_root):
            root=forbidden.resolve()
            if output.is_relative_to(root) or root.is_relative_to(output):
                raise ValueError('Resultat må ligge utenfor både kilder og uttrekk')
        if output.exists():
            raise FileExistsError('Eksisterende XSD-rapport overskrives ikke')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as handle:
            json.dump(report,handle,ensure_ascii=False,indent=2)
            handle.write('\n')
    except (OSError,ValueError,KeyError) as exc:
        parser.error(str(exc))
    print(output)
    for item in report['xml_records']:
        print(f"{item['xml_file']}: {item['technical_xsd_status']}")
    print('Teknisk XSD-validering er ikke full normativ Noark-kontroll.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
