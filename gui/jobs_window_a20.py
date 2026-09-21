from __future__ import annotations

from pathlib import Path
import re
from tkinter import StringVar, filedialog, messagebox

import customtkinter as ctk

from app.storage_layouts import (
    materialize_storage_roles,
    storage_layout_by_id,
    suggested_job_name,
)
from app.workflow_sequences import workflow_sequence_by_id
from noark5_workflow.core.job import Job, JobStatus
from noark5_workflow.core.output_subfolder import (
    OutputSubfolderRuleError,
    effective_work_operations,
    render_output_subfolder_rule,
)
from noark5_workflow.core.result_inventory import scan_result_inventory
from noark5_workflow.plugins.noark5.discovery import discover_from_robocopy_logs
from settings import load_config, save_config
from . import theme
from .discovered_sources_dialog import DiscoveredSourcesDialog
from .jobs_window_a19 import A19JobsWindow


class A20JobsWindow(A19JobsWindow):
    """a16.4.8: job-list output rule plus result-aware job discovery."""

    def __init__(
        self,
        *args,
        get_output_subfolder_rule=None,
        set_output_subfolder_rule=None,
        **kwargs,
    ) -> None:
        self.get_output_subfolder_rule = get_output_subfolder_rule or (lambda: "")
        self.set_output_subfolder_rule = set_output_subfolder_rule or (lambda _rule: (True, ""))
        super().__init__(*args, **kwargs)

        # Keep the inherited job list in row 3. Moving the CTkScrollableFrame
        # after construction can split/overlap already rendered job cards.
        # The list remains the only expanding row; the list-level rule is placed
        # below it and above the summary.
        self.list_frame.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="nsew")
        self.summary.grid(row=5, column=0, padx=18, pady=(2, 14), sticky="w")
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=0)

        frame = ctk.CTkFrame(self, fg_color=theme.PANEL_BG_DARK, corner_radius=8)
        frame.grid(row=4, column=0, padx=18, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame,
            text="Undermappe-regel for Work - operations",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        ).grid(row=0, column=0, padx=(12, 8), pady=(8, 4), sticky="w")

        self.output_rule_var = StringVar(value=self.get_output_subfolder_rule())
        ctk.CTkEntry(
            frame,
            textvariable=self.output_rule_var,
            placeholder_text="<jobno>",
        ).grid(row=0, column=1, padx=8, pady=(8, 4), sticky="ew")

        ctk.CTkButton(
            frame,
            text="Bruk regel",
            width=92,
            command=self._apply_output_rule,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
        ).grid(row=0, column=2, padx=(8, 12), pady=(8, 4))

        ctk.CTkLabel(
            frame,
            text="Tom = ingen | <jobno> <jobid> <nnn> <name> <source>",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 4), sticky="w")

        self.output_rule_preview = ctk.CTkLabel(
            frame,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            justify="left",
            anchor="w",
        )
        self.output_rule_preview.grid(row=2, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="ew")
        self._refresh_output_rule_preview()

    def _apply_output_rule(self) -> None:
        ok, message = self.set_output_subfolder_rule(self.output_rule_var.get())
        if not ok:
            messagebox.showerror("Noark 5 Workflow Manager", message)
            return
        self.output_rule_var.set(self.get_output_subfolder_rule())
        self._refresh_output_rule_preview()
        self.refresh()

    def _refresh_output_rule_preview(self) -> None:
        rule = self.output_rule_var.get().strip()
        rows = []
        for position, job in enumerate(self.batch.jobs()[:6], start=1):
            try:
                sub = render_output_subfolder_rule(rule, job, position)
            except OutputSubfolderRuleError as exc:
                self.output_rule_preview.configure(text=f"Ugyldig regel: {exc}")
                return
            shown = sub or "(ingen undermappe)"
            rows.append(f"{job.job_id} -> {shown}")
        if len(self.batch.jobs()) > 6:
            rows.append(f"... og {len(self.batch.jobs()) - 6} jobb(er) til")
        self.output_rule_preview.configure(text=" | ".join(rows) if rows else "(ingen jobber)")

    @staticmethod
    def _latest_test_progress(job: Job) -> tuple[int, int] | None:
        """Return the latest TEST START/SLUTT n/total seen for a running job."""
        pattern = re.compile(r"\bTEST (?:START|SLUTT)\s+(\d+)/(\d+)\b")
        for entry in reversed(list(getattr(job, "log_entries", ()) or ())[-200:]):
            match = pattern.search(str(entry))
            if match:
                return int(match.group(1)), int(match.group(2))
        return None

    @classmethod
    def _progress_text(cls, job: Job) -> str:
        percent = f"{float(job.progress or 0.0):.0%}"
        if job.status != JobStatus.RUNNING or not job.workflow_ids:
            return percent

        total_operations = len(job.workflow_ids)
        current_operation = max(
            1,
            min(int(job.next_operation_index or 0) + 1, total_operations),
        )
        parts = [f"Operasjon {current_operation}/{total_operations}"]

        test_progress = cls._latest_test_progress(job)
        if test_progress is not None:
            current_test, total_tests = test_progress
            parts.append(f"Test {current_test}/{total_tests}")

        parts.append(percent)
        return " · ".join(parts)

    def _update_row_view(
        self,
        row: int,
        job: Job,
        *,
        active: bool,
        can_move_up: bool,
        can_move_down: bool,
    ) -> None:
        super()._update_row_view(
            row,
            job,
            active=active,
            can_move_up=can_move_up,
            can_move_down=can_move_down,
        )
        view = self._row_views.get(job.job_id)
        if view is None:
            return

        # A bare percentage is ambiguous during long operations. Show workflow
        # position and, when available, the current test position as well.
        view["progress"].configure(
            text=self._progress_text(job),
            width=250 if job.status == JobStatus.RUNNING else 70,
        )

        inventory = str(getattr(job, "_result_inventory_summary", "") or "").strip()
        base_message = str(job.message or "").strip()
        parts = []
        if inventory:
            parts.append(f"Eksisterende: {inventory}")
        if base_message:
            parts.append(base_message)
        view["message"].configure(text=" | ".join(parts))

    def _inventory_for_candidate(self, candidate, *, layout_id: str):
        extraction_root = Path(candidate.path)
        roles = materialize_storage_roles(extraction_root, layout_id=layout_id)
        base = roles.get("work_operations")

        # Discovery is deliberately conservative: scan the whole configured
        # Work - operations base. a16.4.7+ manifests are source-filtered.
        return scan_result_inventory(
            Path(base) if base is not None else None,
            source_extraction=extraction_root,
        )

    def _discover_jobs(self) -> None:
        if self._batch_running:
            return

        settings = load_config()
        kwargs = {
            "title": "Velg Robocopy /L-logg(er) med Noark 5-struktur",
            "filetypes": [
                ("Robocopy/loggfiler", "*.log *.txt"),
                ("Loggfiler", "*.log"),
                ("Tekstfiler", "*.txt"),
                ("Alle filer", "*.*"),
            ],
        }
        previous = str(settings.get("last_noark_discovery_log_dir", "") or "").strip()
        if previous and Path(previous).is_dir():
            kwargs["initialdir"] = previous

        selected_files = filedialog.askopenfilenames(**kwargs)
        if not selected_files:
            return

        paths = [Path(value) for value in selected_files]
        save_config({"last_noark_discovery_log_dir": str(paths[0].parent)})

        try:
            candidates = discover_from_robocopy_logs(paths)
        except Exception as exc:
            messagebox.showerror(
                "Noark 5 Workflow Manager",
                f"Kunne ikke lese Robocopy-loggen(e).\n\n{exc}",
            )
            return

        if not candidates:
            messagebox.showinfo(
                "Noark 5 Workflow Manager",
                "Ingen mulige Noark 5-uttrekk ble funnet.",
            )
            return

        layout_id = str(
            settings.get("storage_layout_profile", "ikamr_standard") or "none"
        )

        existing_sources = {
            str(job.active_extraction_root)
            for job in self.batch.jobs()
            if job.active_extraction_root is not None
        }
        dialog = DiscoveredSourcesDialog(
            self,
            candidates,
            existing_sources=existing_sources,
            result_inventory_provider=lambda candidate: self._inventory_for_candidate(
                candidate,
                layout_id=layout_id,
            ),
        )
        self.wait_window(dialog)

        chosen = dialog.selected
        if not chosen:
            return

        workflow_sequence_id = str(
            settings.get("noark5_discovery_workflow", "noark5_standard") or "none"
        )
        workflow_sequence = workflow_sequence_by_id(workflow_sequence_id)

        created: list[Job] = []
        jobs = self.batch.jobs()

        if jobs and all(job.is_unused_draft() for job in jobs):
            reusable_draft = jobs[0]
            for extra in jobs[1:]:
                self.batch.remove(extra.job_id)
            jobs = self.batch.jobs()
        else:
            reusable_draft = (
                jobs[0] if len(jobs) == 1 and jobs[0].is_unused_draft() else None
            )

        owner_identity = next(
            (job.owner_identity for job in jobs if job.owner_identity), None
        )

        for index, candidate in enumerate(chosen):
            extraction_root = Path(candidate.path)
            roles = materialize_storage_roles(extraction_root, layout_id=layout_id)
            name = suggested_job_name(extraction_root, layout_id=layout_id)

            if index == 0 and reusable_draft is not None:
                job = reusable_draft
                self._apply_roles(job, roles)
                job.name = name
            else:
                job = self.batch.new_job(
                    roles.get("source_root") or extraction_root,
                    name=name,
                )
                self._apply_roles(job, roles)
                job.set_owner_identity(owner_identity)

            job.profile_id = "noark5"
            if workflow_sequence is not None:
                job.set_workflow(workflow_sequence.operation_ids)

            inventory = dialog.inventories.get(dialog._key(candidate.path))
            if dialog.check_existing_results and inventory is not None:
                job._result_inventory_summary = str(
                    getattr(inventory, "summary", "Ingen resultater funnet")
                )
            else:
                job._result_inventory_summary = ""

            if dialog.reset_execution_state:
                job.reset_execution(
                    "Kjørestatus nullstilt - tidligere resultatfiler beholdt"
                )

            created.append(job)

        self._persist_list_change()
        self.refresh()
        self._refresh_output_rule_preview()

        workflow_text = (
            f"Workflow: {workflow_sequence.name} "
            f"({len(workflow_sequence.operation_ids)} operasjoner)."
            if workflow_sequence is not None
            else "Workflow: ingen automatisk tildeling."
        )

        checked_text = ""
        if dialog.check_existing_results:
            selected_inventories = [
                dialog.inventories.get(dialog._key(candidate.path))
                for candidate in chosen
            ]
            with_results = sum(
                1 for inventory in selected_inventories
                if inventory is not None and getattr(inventory, "has_results", False)
            )
            checked_text = (
                f"\nResultatkontroll: {with_results} av {len(chosen)} valgte jobb(er) "
                "har eksisterende resultatdata."
            )
            if dialog.reset_execution_state:
                checked_text += (
                    "\nKjørestatus/cursor er nullstilt. Resultatfiler og logger på disk "
                    "er ikke slettet."
                )

        messagebox.showinfo(
            "Noark 5 Workflow Manager",
            f"{len(created)} jobb(er) ble lagt til jobblisten.\n\n"
            + (
                "Source/Work/Storage er automatisk fylt fra valgt mappeoppsett.\n"
                if layout_id != "none"
                else "Source extraction er satt. Andre mapper fylles ikke automatisk.\n"
            )
            + workflow_text
            + checked_text,
        )
