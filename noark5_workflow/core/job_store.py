from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from .job import Job, JobBatch, JobStatus

FILE_TYPE="noark5-workflow-manager-job-list"
FORMAT_VERSION=4
SUPPORTED_FORMAT_VERSIONS={1,2,3,4}
FILE_EXTENSION=".n5jobs"
class JobListFormatError(ValueError): pass

@dataclass(frozen=True)
class LoadedJobList:
    batch: JobBatch
    active_job_id: str|None
    created_at: str
    modified_at: str
    app_version: str
    output_subfolder_rule: str = ""

def _now_iso()->str: return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _json_value(value:Any)->Any:
    if isinstance(value,Path): return str(value)
    if isinstance(value,Enum): return value.value
    if isinstance(value,dict): return {str(k):_json_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_json_value(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)): return value
    raise TypeError(f"Kan ikke lagre verdi av type {type(value).__name__} i jobblisten")
def _path_text(value:Path|None)->str|None: return str(value) if value is not None else None

def _job_to_dict(job:Job)->dict[str,Any]:
    return {"job_id":job.job_id,"name":job.name,"profile_id":job.profile_id,"source_root":_path_text(job.source_root),
        "source_tar":_path_text(job.source_tar),"source_unzipped":_path_text(job.source_unzipped),
        "source_extraction":_path_text(job.source_extraction),"work_root":_path_text(job.work_root),
        "work_content":_path_text(job.work_content),"work_operations":_path_text(job.work_operations),
        "archive_root":_path_text(job.archive_root),"output_root":_path_text(job.output_root),
        "workflow_ids":list(job.workflow_ids),"operation_params":_json_value(job.operation_params),
        "status":job.status.value,"progress":float(job.progress),"worker":job.worker,"message":job.message,
        "log_entries":list(job.log_entries),"checkpoint_after":list(job.checkpoint_after),
        "next_operation_index":int(job.next_operation_index),
        "owner_user_id":job.owner_user_id,"owner_username":job.owner_username,
        "owner_name":job.owner_name,"owner_email":job.owner_email}
def _optional_path(data:dict[str,Any],key:str)->Path|None:
    value=data.get(key); return Path(str(value)) if value else None

def _job_from_dict(data:dict[str,Any],*,format_version:int)->Job:
    job_id=str(data.get("job_id","")).strip(); source_root=str(data.get("source_root","") or "").strip()
    if not job_id: raise JobListFormatError("Jobb mangler job_id")
    if format_version < 3 and not source_root: raise JobListFormatError(f"{job_id} mangler source_root")
    try: status=JobStatus(data.get("status",JobStatus.READY.value))
    except ValueError: status=JobStatus.READY
    message=str(data.get("message",""))
    if status==JobStatus.RUNNING: status=JobStatus.READY; message="Forrige kjøring var aktiv da jobblisten ble lagret"
    try: progress=max(0.0,min(1.0,float(data.get("progress",0.0))))
    except (TypeError,ValueError): progress=0.0
    params=data.get("operation_params",{})
    if not isinstance(params,dict): raise JobListFormatError(f"{job_id} har ugyldige operation_params")
    workflow_ids=data.get("workflow_ids",[])
    if not isinstance(workflow_ids,list): raise JobListFormatError(f"{job_id} har ugyldig workflow_ids")
    logs=data.get("log_entries",[]); logs=logs if isinstance(logs,list) else []
    checkpoints=data.get("checkpoint_after",[]) if format_version>=2 else []
    checkpoints=checkpoints if isinstance(checkpoints,list) else []
    try: next_index=int(data.get("next_operation_index",0)) if format_version>=2 else 0
    except (TypeError,ValueError): next_index=0
    output_root=_optional_path(data,"output_root")
    return Job(job_id=job_id,source_root=Path(source_root) if source_root else None,output_root=output_root,
        source_tar=_optional_path(data,"source_tar") if format_version>=3 else None,
        source_unzipped=_optional_path(data,"source_unzipped") if format_version>=3 else None,
        source_extraction=_optional_path(data,"source_extraction") if format_version>=3 else None,
        work_root=_optional_path(data,"work_root") if format_version>=3 else None,
        work_content=_optional_path(data,"work_content") if format_version>=3 else None,
        work_operations=_optional_path(data,"work_operations") if format_version>=3 else None,
        archive_root=_optional_path(data,"archive_root") if format_version>=3 else output_root,
        name=str(data.get("name","")),profile_id=(str(data.get("profile_id")).strip() if data.get("profile_id") else None),workflow_ids=[str(v) for v in workflow_ids],operation_params=_json_value(params),
        status=status,progress=progress,worker=str(data.get("worker","Lokal (denne PC-en)")),message=message,
        log_entries=[str(v) for v in logs][-2000:],checkpoint_after=[str(v) for v in checkpoints],next_operation_index=next_index,
        owner_user_id=str(data.get("owner_user_id","") or ""),owner_username=str(data.get("owner_username","") or ""),
        owner_name=str(data.get("owner_name","") or ""),owner_email=str(data.get("owner_email","") or ""))

def _existing_created_at(path:Path)->str|None:
    if not path.is_file(): return None
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return None
    if isinstance(data,dict) and data.get("file_type")==FILE_TYPE:
        value=str(data.get("created_at","")).strip(); return value or None
    return None

def save_job_list(path:Path,batch:JobBatch,*,active_job_id:str|None=None,app_version:str="")->Path:
    path=Path(path)
    if path.suffix.lower()!=FILE_EXTENSION: path=path.with_suffix(FILE_EXTENSION)
    path.parent.mkdir(parents=True,exist_ok=True); now=_now_iso()
    payload={"file_type":FILE_TYPE,"format_version":FORMAT_VERSION,"app_version":app_version,
        "created_at":_existing_created_at(path) or now,"modified_at":now,"active_job_id":active_job_id,
        "output_subfolder_rule":str(getattr(batch,"output_subfolder_rule","") or ""),
        "jobs":[_job_to_dict(job) for job in batch.jobs()]}
    temp_path=path.with_name(path.name+".tmp")
    try:
        temp_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); temp_path.replace(path)
    finally:
        if temp_path.exists():
            try: temp_path.unlink()
            except OSError: pass
    return path

def load_job_list(path:Path)->LoadedJobList:
    path=Path(path)
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc: raise JobListFormatError(f"Kunne ikke lese jobblisten: {exc}") from exc
    except json.JSONDecodeError as exc: raise JobListFormatError(f"Ugyldig JSON i jobblisten: {exc}") from exc
    if not isinstance(data,dict): raise JobListFormatError("Jobblisten må inneholde et JSON-objekt")
    if data.get("file_type")!=FILE_TYPE: raise JobListFormatError("Filen er ikke en Noark 5 Workflow Manager-jobbliste")
    version=data.get("format_version")
    if version not in SUPPORTED_FORMAT_VERSIONS: raise JobListFormatError(f"Jobblisteformat {version!r} støttes ikke (støttede versjoner: {sorted(SUPPORTED_FORMAT_VERSIONS)})")
    raw_jobs=data.get("jobs",[])
    if not isinstance(raw_jobs,list): raise JobListFormatError("Feltet jobs må være en liste")
    batch=JobBatch()
    for raw in raw_jobs:
        if not isinstance(raw,dict): raise JobListFormatError("Ugyldig jobb i jobs-listen")
        batch.add(_job_from_dict(raw,format_version=int(version)))
    rule=str(data.get("output_subfolder_rule","") or "") if int(version)>=4 else ""
    batch.output_subfolder_rule=rule
    active=data.get("active_job_id")
    if active is not None:
        active=str(active)
        if batch.get(active) is None: active=None
    return LoadedJobList(batch=batch,active_job_id=active,created_at=str(data.get("created_at","")),modified_at=str(data.get("modified_at","")),app_version=str(data.get("app_version","")),output_subfolder_rule=rule)
