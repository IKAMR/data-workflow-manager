from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from lxml import etree

from noark5_workflow.analysis import a13_large_xml
from noark5_workflow import a13_xpath_worker
from gui.persistent_app_a13_runtime import WorkflowApp


class _FakePipe:
    def __init__(self, lines):
        self._lines = iter(lines)
    def readline(self):
        try:
            return next(self._lines)
        except StopIteration:
            return ""
    def close(self):
        pass


class _FakePopen:
    last_request = None

    def __init__(self, args, **kwargs):
        request_path = Path(args[-2])
        result_path = Path(args[-1])
        type(self).last_request = json.loads(request_path.read_text(encoding="utf-8"))
        result_path.write_text(json.dumps({"ok": True, "index": {"summary": {"ok": 1}}}), encoding="utf-8")
        event = {
            "kind": "test_progress",
            "phase": "finished",
            "current": 1,
            "total": 1,
            "test": {"test_id": "x"},
            "status": "ok",
            "duration": 0.1,
        }
        self.stdout = _FakePipe(["DWM_A13_EVENT\t" + json.dumps(event) + "\n"])
        self.stderr = _FakePipe([])
        self.returncode = 0
        self._polls = 0
    def poll(self):
        self._polls += 1
        return None if self._polls == 1 else 0


class A13RuntimeIsolationTests(unittest.TestCase):
    def test_xpath_profile_is_process_isolated_and_forwards_progress(self):
        seen = []
        with tempfile.TemporaryDirectory() as td, patch.object(a13_large_xml.subprocess, "Popen", _FakePopen):
            out = Path(td) / "out"
            index = a13_large_xml._run_catalog_profiled_isolated(
                "catalog.json",
                "source",
                out,
                progress_callback=lambda *args: seen.append(args),
            )
        self.assertEqual(index["summary"]["ok"], 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "finished")
        self.assertEqual(seen[0][1:3], (1, 1))
        self.assertEqual(
            Path(_FakePopen.last_request["stderr_path"]).name,
            "xpath-worker-stderr.log",
        )

    def test_runtime_mode_reports_subprocess(self):
        self.assertEqual(a13_large_xml._environment()["xpath_execution_mode"], "subprocess")
        self.assertEqual(a13_large_xml._environment()["large_xml_mode"], "auto-iterator-cache")

    def test_worker_installs_large_xml_runtime_in_child(self):
        with patch(
            "noark5_workflow.analysis.a13_large_xml.install"
        ) as install_mock:
            a13_xpath_worker._install_large_xml_runtime()
        install_mock.assert_called_once_with()

    def test_worker_redirects_native_stderr_descriptor(self):
        fake_fd = 17
        with patch.object(a13_xpath_worker.os, "open", return_value=fake_fd) as open_mock, \
             patch.object(a13_xpath_worker.os, "dup2") as dup2_mock, \
             patch.object(a13_xpath_worker.os, "close") as close_mock, \
             tempfile.TemporaryDirectory() as td:
            target = Path(td) / "native-stderr.log"
            a13_xpath_worker._redirect_native_stderr(target)
        open_mock.assert_called_once()
        dup2_mock.assert_called_once_with(fake_fd, 2)
        close_mock.assert_called_once_with(fake_fd)

    def test_worker_windows_redirect_updates_native_standard_error_handle(self):
        fake_fd = 17
        fake_handle = 12345
        fake_kernel32 = Mock()
        fake_ctypes = SimpleNamespace(
            c_void_p=lambda value: value,
            windll=SimpleNamespace(kernel32=fake_kernel32),
        )
        fake_msvcrt = SimpleNamespace(get_osfhandle=lambda fd: fake_handle)
        with patch.object(a13_xpath_worker.os, "name", "nt"), \
             patch.object(a13_xpath_worker.os, "open", return_value=fake_fd), \
             patch.object(a13_xpath_worker.os, "dup2"), \
             patch.object(a13_xpath_worker.os, "close"), \
             patch.dict("sys.modules", {"ctypes": fake_ctypes, "msvcrt": fake_msvcrt}), \
             tempfile.TemporaryDirectory() as td:
            a13_xpath_worker._redirect_native_stderr(Path(td) / "stderr.log")
        fake_kernel32.SetStdHandle.assert_called_once_with(-12, fake_handle)

    def test_main_source_selection_recovers_single_visible_job(self):
        extraction = Path(r"C:\\arkiv-noark5\\1543\\new\\content\\sip\\content")
        job = SimpleNamespace(
            source_root=None,
            source_tar=None,
            source_unzipped=None,
            source_extraction=None,
            work_root=None,
            work_content=None,
            work_operations=None,
            archive_root=None,
        )
        captured = {}
        fake_self = SimpleNamespace(
            settings={"storage_layout_profile": "ikamr_standard"},
            current_job=None,
            jobs=SimpleNamespace(jobs=lambda: [job]),
            _ensure_job_for_current_source=lambda: None,
            _refresh_active_job_label=lambda: None,
            _save_storage_roles=lambda _job, values: captured.update(values),
        )
        suggestions = {"source_extraction": extraction}
        with patch(
            "gui.persistent_app_a13_runtime.suggest_storage_roles",
            return_value=suggestions,
        ), patch(
            "gui.persistent_app_a13_runtime.messagebox.showwarning"
        ) as warning_mock:
            WorkflowApp._source_browse_complete(fake_self, extraction)

        self.assertIs(fake_self.current_job, job)
        self.assertEqual(captured["source_extraction"], extraction)
        warning_mock.assert_not_called()

    def test_main_source_selection_can_replace_related_storage_roles(self):
        old_root = Path(r"G:\\arkiv-noark5\\1543\\old")
        new_root = Path(r"C:\\arkiv-noark5\\1543\\new")
        extraction = new_root / "content" / "sip" / "content"
        job = SimpleNamespace(
            source_root=old_root,
            source_tar=None,
            source_unzipped=None,
            source_extraction=extraction,
            work_root=old_root,
            work_content=old_root / "content",
            work_operations=old_root / "repository_operations",
            archive_root=old_root / "aip",
        )
        captured = {}
        fake_self = SimpleNamespace(
            settings={"storage_layout_profile": "ikamr_standard"},
            _ensure_job_for_current_source=lambda: job,
            _save_storage_roles=lambda _job, values: captured.update(values),
        )
        suggestions = {
            "source_root": new_root,
            "source_extraction": extraction,
            "work_root": new_root,
            "work_content": new_root / "content",
            "work_operations": new_root / "repository_operations",
            "archive_root": new_root / "aip",
        }
        with patch(
            "gui.persistent_app_a13_runtime.suggest_storage_roles",
            return_value=suggestions,
        ), patch(
            "gui.persistent_app_a13_runtime.messagebox.askyesno",
            return_value=True,
        ) as ask_mock:
            WorkflowApp._source_browse_complete(fake_self, extraction)

        self.assertEqual(captured["source_root"], new_root)
        self.assertEqual(captured["source_extraction"], extraction)
        self.assertEqual(captured["work_operations"], new_root / "repository_operations")
        self.assertEqual(captured["archive_root"], new_root / "aip")
        ask_mock.assert_called_once()


    def test_c01_streaming_values_do_not_need_xpath_nodesets(self):
        root = etree.fromstring(
            b"""<arkiv>
              <systemID>A</systemID><tittel>Archive</tittel><arkivstatus>Avsluttet</arkivstatus>
              <arkivskaper><arkivskaperNavn>Creator</arkivskaperNavn><arkivskaperID>C1</arkivskaperID></arkivskaper>
              <arkivdel><mappe><registrering/></mappe></arkivdel>
            </arkiv>"""
        )
        values = a13_large_xml._c01_values_streaming(etree.ElementTree(root))
        self.assertEqual(values["archive_count"], 1)
        self.assertEqual(values["archive_creator_count"], 1)
        self.assertEqual(values["archive_records"][0]["system_id"], "A")
        self.assertEqual(values["archive_creator_records"][0]["id"], "C1")
        self.assertEqual(values["archive_status_counts"], {"Avsluttet": 1})

    def test_c01_file_iterparse_avoids_full_tree_and_handles_namespaces(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <arkiv xmlns='urn:noark:test'>
          <systemID>A</systemID><tittel>Archive</tittel><beskrivelse>Desc</beskrivelse>
          <arkivstatus>Avsluttet</arkivstatus><dokumentmedium>Elektronisk arkiv</dokumentmedium>
          <opprettetDato>2020-01-02</opprettetDato><avsluttetDato>2022-02-03</avsluttetDato>
          <opprettetAv>u1</opprettetAv><avsluttetAv>u2</avsluttetAv>
          <arkivskaper><arkivskaperNavn>Creator</arkivskaperNavn><arkivskaperID>C1</arkivskaperID><beskrivelse>Creator desc</beskrivelse></arkivskaper>
          <arkivdel><mappe><registrering/></mappe></arkivdel>
        </arkiv>"""
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "arkivstruktur.xml"
            source.write_bytes(xml)
            with patch.object(
                a13_large_xml, "_normalise_tree_scalable",
                side_effect=AssertionError("C01 file streaming must not build a full tree"),
            ):
                values = a13_large_xml._c01_values_iterparse_file(source)
        self.assertEqual(values["archive_count"], 1)
        self.assertEqual(values["archive_creator_count"], 1)
        self.assertEqual(values["archive_records"][0]["system_id"], "A")
        self.assertEqual(values["archive_records"][0]["status"], "Avsluttet")
        self.assertEqual(values["archive_creator_records"][0]["id"], "C1")
        self.assertEqual(values["archive_status_counts"], {"Avsluttet": 1})

    def test_c02_streaming_values_do_not_need_large_xpath_nodesets(self):
        root = etree.fromstring(
            b"""<arkiv>
              <arkivdel><systemID>A1</systemID><tittel>One</tittel><arkivdelstatus>Avsluttet periode</arkivdelstatus>
                <opprettetDato>2020-01-02</opprettetDato><avsluttetDato>2022-02-03</avsluttetDato>
                <mappe><registrering><dokumentbeskrivelse><dokumentmedium>Elektronisk arkiv</dokumentmedium></dokumentbeskrivelse></registrering></mappe>
              </arkivdel>
              <arkivdel><systemID>A2</systemID><tittel>Two</tittel><arkivdelstatus>Avsluttet periode</arkivdelstatus>
                <opprettetDato>2019-01-02</opprettetDato><avsluttetDato>2023-02-03</avsluttetDato>
                <mappe/><mappe><registrering/></mappe>
              </arkivdel>
            </arkiv>"""
        )
        tree = etree.ElementTree(root)
        fake_engine = SimpleNamespace(_reconcile=lambda values, rows, specs: {})
        values = a13_large_xml._c02_values_streaming(
            tree,
            {"reconciliation": []},
            fake_engine,
        )
        self.assertEqual(values["archive_part_count"], 2)
        self.assertEqual(values["folder_count"], 3)
        self.assertEqual(values["registration_count"], 2)
        self.assertEqual(values["document_description_count"], 1)
        self.assertEqual(values["document_medium_counts"], {"Elektronisk arkiv": 1})
        self.assertEqual(values["archive_part_created_date_range"]["first"], "2019-01-02")
        self.assertEqual(values["archive_part_closed_date_range"]["last"], "2023-02-03")

    def test_c02_file_iterparse_avoids_full_tree_and_handles_namespaces(self):
        xml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <arkiv xmlns='urn:noark:test'>
          <arkivdel><systemID>A1</systemID><tittel>One</tittel><arkivdelstatus>Avsluttet periode</arkivdelstatus>
            <opprettetDato>2020-01-02</opprettetDato><avsluttetDato>2022-02-03</avsluttetDato>
            <mappe><registrering><dokumentbeskrivelse><dokumentmedium>Elektronisk arkiv</dokumentmedium></dokumentbeskrivelse></registrering></mappe>
          </arkivdel>
          <arkivdel><systemID>A2</systemID><tittel>Two</tittel><arkivdelstatus>Avsluttet periode</arkivdelstatus>
            <opprettetDato>2019-01-02</opprettetDato><avsluttetDato>2023-02-03</avsluttetDato>
            <mappe/><mappe><registrering/></mappe>
          </arkivdel>
        </arkiv>"""
        fake_engine = SimpleNamespace(_reconcile=lambda values, rows, specs: {})
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "arkivstruktur.xml"
            source.write_bytes(xml)
            values = a13_large_xml._c02_values_iterparse_file(
                source,
                {"reconciliation": []},
                fake_engine,
            )
        self.assertEqual(values["archive_part_count"], 2)
        self.assertEqual(values["folder_count"], 3)
        self.assertEqual(values["registration_count"], 2)
        self.assertEqual(values["document_description_count"], 1)
        self.assertEqual(values["document_medium_counts"], {"Elektronisk arkiv": 1})
        self.assertEqual(values["archive_part_records"][0]["system_id"], "A1")
        self.assertEqual(values["archive_part_created_date_range"]["first"], "2019-01-02")
        self.assertEqual(values["archive_part_closed_date_range"]["last"], "2023-02-03")

    def test_worker_forces_utf8_stdio_when_supported(self):
        out = Mock()
        err = Mock()
        with patch.object(a13_xpath_worker.sys, "stdout", out), patch.object(
            a13_xpath_worker.sys, "stderr", err
        ):
            a13_xpath_worker._force_utf8_stdio()
        out.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        err.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_standard_setup_syncs_active_job_into_main_workflow(self):
        job = SimpleNamespace(profile_id="noark5", workflow_ids=["one", "two"])
        workflow = Mock()
        panel = Mock()
        fake_self = SimpleNamespace(
            current_job=job,
            workflow=workflow,
            workflow_panel=panel,
            _apply_profile=Mock(),
            _apply_job_operation_params=Mock(),
            _refresh_active_job_label=Mock(),
            _update_run_button=Mock(),
        )
        WorkflowApp._sync_active_job_to_main(fake_self, job)
        workflow.clear.assert_called_once_with()
        self.assertEqual(workflow.add.call_args_list, [unittest.mock.call("one"), unittest.mock.call("two")])
        panel.refresh.assert_called_once_with()
        fake_self._refresh_active_job_label.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
