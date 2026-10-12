"""Resource planning for Noark 5 analysis. No concurrent execution is started here.

Separate worker limits for XPath and external document tools. Conservative
memory estimates protect smaller laptops and leave space for the OS.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


def physical_memory_gib() -> float | None:
    try:
        if os.name == 'nt':
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('memory_load', ctypes.c_ulong),
                    ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                    ('total_page_file', ctypes.c_ulonglong), ('avail_page_file', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                    ('avail_extended_virtual', ctypes.c_ulonglong)]
            info = MemoryStatus()
            info.length = ctypes.sizeof(info)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
                return round(info.total_phys / (1024 ** 3), 2)
        else:
            with open('/proc/meminfo', encoding='ascii') as fd:
                for line in fd:
                    if line.startswith('MemTotal:'):
                        return round(int(line.split()[1]) / (1024 ** 2), 2)
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _integer(value: object, default: int) -> int:
    try:
        v = int(value)
        return v if v >= 0 else default
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class AnalysisResources:
    cpu_count: int
    memory_gib: float | None
    xpath_workers: int
    document_workers: int
    parallel_jobs: int
    xpath_timeout_minutes: int
    document_timeout_minutes: int
    rationale: str


def resource_plan(settings: Mapping[str, object], *, cpu_count: int | None = None,
                  memory_gib: float | None = None) -> AnalysisResources:
    cpu = max(1, cpu_count if cpu_count is not None else (os.cpu_count() or 1))
    ram = memory_gib if memory_gib is not None else physical_memory_gib()
    # A large XML tree can occupy many GiB per worker. Avoid automatic
    # duplication; shared-tree safety must be verified before raising this.
    xpath_auto = 1
    # External document scanners are independent tools and may each recurse
    # the same files. No simultaneous scans until isolated outputs are proven.
    doc_auto = 1
    configured_xpath = _integer(settings.get('noark5_xpath_workers', 0), 0)
    configured_doc = _integer(settings.get('document_analysis_workers', 0), 0)
    xpath = min(cpu, configured_xpath) if configured_xpath else xpath_auto
    doc = min(cpu, configured_doc) if configured_doc else doc_auto
    return AnalysisResources(cpu, ram, max(1, xpath), max(1, doc), 1,
        _integer(settings.get('xpath_timeout_minutes', 0), 0),
        _integer(settings.get('document_timeout_minutes', 0), 0),
        'Konfigurasjon og kapasitetsplan. Selve analyseadapterne maa aktivere parallellkjoring eksplisitt.')


def validate_resource_settings(settings: Mapping[str, object]) -> dict[str, int]:
    keys = ('noark5_xpath_workers', 'document_analysis_workers',
            'xpath_timeout_minutes', 'document_timeout_minutes')
    result = {}
    for key in keys:
        value = settings.get(key, 0)
        try:
            n = int(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'{key}: ma vaere et heltall') from exc
        if n < 0 or (key.endswith('_workers') and n > 64):
            raise ValueError(f'{key}: ugyldig verdi {n}')
        result[key] = n
    return result
