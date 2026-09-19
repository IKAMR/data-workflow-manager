from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULT_CONFIG = {
    "execution_backend": "local",
    "remote_endpoint": "",
    "shared_storage_root": "",
    "temp_dir": "",
    "run_log_dir": "",
    "setup_dir": "",
    "job_list_dir": "",
    "log_level": "INFO",
    "enabled_log_sinks": ["text_run_log", "premis"],
    "operation_visibility": 2,
    "appearance_mode": "dark",
    "font_offset": 0,
    "restore_main_window_position": True,
    "restore_main_window_size": True,
    "restore_main_window_maximized": True,
    "main_window_x": None,
    "main_window_y": None,
    "main_window_width": None,
    "main_window_height": None,
    "main_window_maximized": False,
    "copy_run_log_to_work_operations": True,
    "last_noark_source_dir": "",
    "last_source_extraction_dir": "",
    "recent_source_extraction_dirs": [],
    "recent_storage_role_paths": {},
    "last_profile_id": "",
    "last_dias_output_dir": "",
    "last_mets_import_dir": "",
    "last_dias_add_file_dir": "",
    "last_dias_add_folder_dir": "",
    "last_setup_dir": "",
    "last_job_list_file": "",
    "last_job_list_dir": "",
    "recent_job_list_dirs": [],
    "recent_job_list_files": [],
    "storage_layout_profile": "ikamr_standard",
    "noark5_discovery_workflow": "noark5_standard",
    "enable_premis_provenance": True,
    "premis_output_dir": "",
    "premis_agent_identifier": "username",
}


def load_config() -> dict:
    data = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_config(changes: dict) -> dict:
    data = load_config()
    data.update(changes)
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data
