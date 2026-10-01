from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

import customtkinter as ctk
from tkinter import messagebox

from noark5_workflow.core.job import Job
from noark5_workflow.external_tools.arkade5 import inspect_arkade5_cli
from noark5_workflow.external_tools.arkade5_jobs import (
    ARKADE5_NOARK5,
    ARKADE5_PRONOM,
    build_arkade5_plan,
    resolve_arkade5_output_subfolder,
)
from . import theme


class Arkade5RunDialog(ctk.CTkToplevel):
    """Review selected jobs and show live status while Arkade 5 is running."""

    def __init__(
        self,
        master,
        settings: dict,
        jobs: Iterable[Job],
        *,
        on_run: Callable[[tuple, Callable, Callable], object],
    ) -> None:
        super().__init__(master)
        self._settings = dict(settings)
        self._jobs = tuple(jobs)
        self._on_run = on_run
        self._run_started: float | None = None
        self._active_run_started: float | None = None
        self._activity_after_id = None
        self._output_after_id = None
        self._output_queue: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._live_lines: list[str] = []
        self._running = False

        self.title("Kjør Arkade 5")
        self.geometry("1120x820")
        self.minsize(880, 640)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        # Job/path summary stays compact; the live Arkade log owns spare height.
        self.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(
            self,
            text="KJØR ARKADE 5",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(22, 6), sticky="ew")

        status = inspect_arkade5_cli(self._settings)
        self._cli_status = status
        ctk.CTkLabel(
            self,
            text=status.message,
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_SUB if status.ok else theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, padx=24, pady=(0, 10), sticky="ew")

        operations = ctk.CTkFrame(self, fg_color=theme.PANEL_BG)
        operations.grid(row=2, column=0, padx=24, pady=(0, 10), sticky="ew")
        operations.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(
            operations,
            text="Operasjoner",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        ).grid(row=0, column=0, padx=(14, 12), pady=12, sticky="w")

        self._noark_var = ctk.BooleanVar(value=True)
        self._pronom_var = ctk.BooleanVar(value=False)
        self._noark_check = ctk.CTkCheckBox(
            operations,
            text="Noark 5-test",
            variable=self._noark_var,
            command=self._refresh_plan,
        )
        self._noark_check.grid(row=0, column=1, padx=10, pady=12, sticky="w")
        self._pronom_check = ctk.CTkCheckBox(
            operations,
            text="PRONOM-analyse (Siegfried)",
            variable=self._pronom_var,
            command=self._refresh_plan,
        )
        self._pronom_check.grid(row=0, column=2, padx=10, pady=12, sticky="w")

        self._plan_label = ctk.CTkLabel(
            operations,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
        )
        self._plan_label.grid(row=0, column=5, padx=14, pady=12, sticky="e")

        ctk.CTkLabel(
            self,
            text=(
                "Hver valgt Arkade-operasjon kjøres som en separat ekstern kjøring på samme DWM-jobb. "
                "Noark 5-test bruker Source - extraction som arkivuttrekk. PRONOM-analyse bruker samme "
                "Source - extraction som analysegrunnlag. Resultater lagres under jobbens Work - operations og "
                "nye resultater fra denne DWM-kjøringen importeres automatisk til samme jobb."
            ),
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            justify="left",
            anchor="w",
            wraplength=1060,
        ).grid(row=3, column=0, padx=24, pady=(0, 10), sticky="ew")

        activity = ctk.CTkFrame(self, fg_color=theme.PANEL_BG)
        activity.grid(row=4, column=0, padx=24, pady=(0, 8), sticky="ew")
        activity.grid_columnconfigure(0, weight=1)
        self._progress = ctk.CTkLabel(
            activity,
            text="",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._progress.grid(row=0, column=0, padx=12, pady=(9, 2), sticky="ew")
        self._elapsed = ctk.CTkLabel(
            activity,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="e",
        )
        self._elapsed.grid(row=0, column=1, padx=12, pady=(9, 2), sticky="e")
        self._activity_bar = ctk.CTkProgressBar(activity, mode="indeterminate")
        self._activity_bar.grid(row=1, column=0, columnspan=2, padx=12, pady=(2, 10), sticky="ew")
        self._activity_bar.set(0)

        # Keep the selected-job/source/work summary compact and above the live log.
        scroll = ctk.CTkScrollableFrame(self, fg_color=theme.PANEL_BG, height=145)
        scroll.grid(row=5, column=0, padx=24, pady=(0, 10), sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)
        for row, job in enumerate(self._jobs):
            source = getattr(job, "active_extraction_root", None)
            work = getattr(job, "work_operations", None)
            name = str(getattr(job, "name", "") or getattr(job, "job_id", ""))
            arkade_folder = self._resolved_arkade_folder()
            arkade_output = (
                str(Path(work) / arkade_folder)
                if work and arkade_folder
                else "(kan ikke beregnes)"
            )
            existing = self._existing_arkade_roots(work)
            existing_text = ""
            if existing and arkade_folder:
                target = Path(work) / arkade_folder
                if not any(root.resolve() == target.resolve() for root in existing):
                    existing_text = (
                        "\nOBS: eksisterende Arkade-lokasjon: "
                        + ", ".join(str(root) for root in existing)
                    )
            text = (
                f"{getattr(job, 'job_id', '')}   {name}\n"
                f"Source: {source or '(ikke valgt)'}\n"
                f"Work - operations: {work or '(ikke valgt)'}\n"
                f"Arkade output: {arkade_output}"
                f"{existing_text}"
            )
            ctk.CTkLabel(
                scroll,
                text=text,
                font=theme.font(theme.SMALL_SIZE),
                text_color=theme.TEXT_MAIN,
                anchor="w",
                justify="left",
                wraplength=1010,
            ).grid(row=row, column=0, padx=12, pady=10, sticky="ew")

        ctk.CTkLabel(
            self,
            text="Live-status fra Arkade",
            font=theme.font(theme.SMALL_SIZE, "bold"),
            text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=6, column=0, padx=24, pady=(2, 3), sticky="ew")
        self._live_log = ctk.CTkTextbox(
            self,
            height=300,
            font=theme.font(theme.SMALL_SIZE),
            fg_color=theme.PANEL_BG,
            text_color=theme.TEXT_MAIN,
            wrap="word",
        )
        self._live_log.grid(row=7, column=0, padx=24, pady=(0, 10), sticky="nsew")
        self._live_log.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=8, column=0, padx=24, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self._run_button = ctk.CTkButton(
            footer,
            text="Kjør valgte",
            width=140,
            command=self._start,
        )
        self._run_button.grid(row=0, column=1, padx=(8, 0), sticky="e")
        self._close_button = ctk.CTkButton(
            footer,
            text="Lukk",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.destroy,
        )
        self._close_button.grid(row=0, column=2, padx=(8, 0), sticky="e")

        self._refresh_plan()

    def _resolved_arkade_folder(self) -> str | None:
        if not self._cli_status.ok:
            return None
        try:
            return resolve_arkade5_output_subfolder(
                self._settings,
                self._cli_status.version or "unknown",
            )
        except Exception:
            return None

    @staticmethod
    def _existing_arkade_roots(work_operations) -> tuple:
        """Find plausible Arkade result roots directly below Work - operations.

        This is deliberately a presentation/consistency aid only. It does not
        alter the authoritative Work - operations role or Arkade output routing.
        """
        from pathlib import Path

        if not work_operations:
            return ()
        root = Path(work_operations)
        try:
            children = tuple(root.iterdir())
        except OSError:
            return ()

        rows = []
        for child in children:
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            name = child.name.lower()
            looks_like_arkade = name.startswith("arkade5")
            has_operation_folders = (child / "noark5").is_dir() or (child / "pronom").is_dir()
            if looks_like_arkade or has_operation_folders:
                rows.append(child)
        return tuple(sorted(rows, key=lambda p: p.name.lower()))

    def _location_mismatches(self) -> tuple[str, ...]:
        configured = self._resolved_arkade_folder()
        if not configured:
            return ()

        messages = []
        for job in self._jobs:
            work = getattr(job, "work_operations", None)
            if not work:
                continue
            roots = self._existing_arkade_roots(work)
            if not roots:
                continue

            target = Path(work) / configured
            # If the configured target already exists, the current setting has
            # a concrete home for this job; older version folders are history,
            # not a mismatch.
            if any(root.resolve() == target.resolve() for root in roots):
                continue

            existing = ", ".join(str(root) for root in roots)
            messages.append(
                f"{getattr(job, 'job_id', '')}: eksisterende Arkade-lokasjon(er):\n"
                f"  {existing}\n"
                f"Ny aktiv setting vil bruke:\n"
                f"  {target}"
            )
        return tuple(messages)

    def _selected_operations(self) -> tuple[str, ...]:
        result: list[str] = []
        if self._noark_var.get():
            result.append(ARKADE5_NOARK5)
        if self._pronom_var.get():
            result.append(ARKADE5_PRONOM)
        return tuple(result)

    def _refresh_plan(self) -> None:
        operations = self._selected_operations()
        count = len(self._jobs) * len(operations)
        self._plan_label.configure(text=f"Plan: {len(self._jobs)} jobb(er) × {len(operations)} = {count} kjøring(er)")
        self._run_button.configure(
            state="normal" if self._cli_status.ok and count and not self._running else "disabled"
        )

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def _tick_elapsed(self) -> None:
        if not self._running or self._run_started is None:
            return
        total = self._format_elapsed(time.monotonic() - self._run_started)
        current = ""
        if self._active_run_started is not None:
            current = self._format_elapsed(time.monotonic() - self._active_run_started)
        self._elapsed.configure(text=f"Denne kjøringen: {current}   Totalt: {total}")
        self._activity_after_id = self.after(1000, self._tick_elapsed)

    def _append_live_line(self, stream_name: str, text: str) -> None:
        clean = text.rstrip("\r\n")
        if not clean:
            return
        prefix = "[stderr] " if stream_name == "stderr" else ""
        self._live_lines.append(prefix + clean)
        self._live_lines = self._live_lines[-40:]
        self._live_log.configure(state="normal")
        self._live_log.delete("1.0", "end")
        self._live_log.insert("1.0", "\n".join(self._live_lines))
        self._live_log.see("end")
        self._live_log.configure(state="disabled")

    def _poll_output(self) -> None:
        if not self._running:
            return
        for _ in range(100):
            try:
                stream_name, text = self._output_queue.get_nowait()
            except queue.Empty:
                break
            self._append_live_line(stream_name, text)
        self._output_after_id = self.after(150, self._poll_output)

    def _start(self) -> None:
        operations = self._selected_operations()
        if not operations:
            return

        mismatches = self._location_mismatches()
        if mismatches:
            message = (
                "Arkade 5 output-undermappen i Setup avviker fra eksisterende "
                "Arkade-lokasjon for én eller flere valgte jobber.\n\n"
                + "\n\n".join(mismatches)
                + "\n\nDette kan være tilsiktet, for eksempel ved ny Arkade-versjon. "
                "Vil du bruke den nye aktive lokasjonen?"
            )
            if not messagebox.askyesno(
                "Arkade 5 – endret output-lokasjon",
                message,
                parent=self,
            ):
                return

        try:
            plans = build_arkade5_plan(self._settings, self._jobs, operations)
        except Exception as exc:
            messagebox.showerror("Data Workflow Manager", str(exc), parent=self)
            return
        expected = len(self._jobs) * len(operations)
        if len(plans) != expected:
            missing = expected - len(plans)
            if not messagebox.askyesno(
                "Data Workflow Manager",
                f"{missing} planlagte kjøring(er) kunne ikke opprettes fordi Source eller Work mangler/ikke er tilgjengelig.\n\nKjøre de {len(plans)} gyldige kjøringene?",
                parent=self,
            ):
                return
        if not plans:
            messagebox.showinfo("Data Workflow Manager", "Ingen kjørbare Arkade 5-jobber.", parent=self)
            return

        self._running = True
        self._run_started = time.monotonic()
        self._active_run_started = self._run_started
        self._live_lines.clear()
        self._live_log.configure(state="normal")
        self._live_log.delete("1.0", "end")
        self._live_log.configure(state="disabled")
        self._run_button.configure(state="disabled")
        self._close_button.configure(state="disabled")
        self._noark_check.configure(state="disabled")
        self._pronom_check.configure(state="disabled")
        self._progress.configure(text=f"Starter {len(plans)} Arkade 5-kjøring(er) …")
        self._activity_bar.start()
        self._tick_elapsed()
        self._poll_output()

        def progress(index: int, total: int, plan, state: str) -> None:
            label = "Noark 5-test" if plan.operation == ARKADE5_NOARK5 else "PRONOM-analyse"
            text = f"{index} av {total}: {plan.job_id} – {label} – {state}"
            if state == "starter":
                self._active_run_started = time.monotonic()
                self._output_queue.put(("stdout", f"--- {text} ---\n"))
            self.after(0, lambda value=text: self._progress.configure(text=value))

        def output(index: int, total: int, plan, stream_name: str, text: str) -> None:
            self._output_queue.put((stream_name, text))

        def worker() -> None:
            try:
                summary = self._on_run(plans, progress, output)
            except Exception as exc:
                self.after(0, lambda: self._finish_error(str(exc)))
                return
            self.after(0, lambda: self._finish(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _stop_activity(self) -> None:
        self._running = False
        self._activity_bar.stop()
        self._activity_bar.set(0)
        if self._activity_after_id is not None:
            try:
                self.after_cancel(self._activity_after_id)
            except Exception:
                pass
            self._activity_after_id = None
        if self._output_after_id is not None:
            try:
                self.after_cancel(self._output_after_id)
            except Exception:
                pass
            self._output_after_id = None
        while True:
            try:
                stream_name, text = self._output_queue.get_nowait()
            except queue.Empty:
                break
            self._append_live_line(stream_name, text)

    def _finish(self, summary) -> None:
        self._stop_activity()
        self._close_button.configure(state="normal")
        self._noark_check.configure(state="normal")
        self._pronom_check.configure(state="normal")
        self._refresh_plan()
        auto = getattr(summary, "auto_import", None)
        import_text = ""
        dialog_import_text = ""
        if auto is not None:
            import_text = (
                f" Import: {auto.imported} ny(e), {auto.already_imported} allerede importert, "
                f"{auto.pronom_attached} PRONOM koblet, "
                f"{auto.failed + auto.pronom_failed} importfeil."
            )
            dialog_import_text = (
                "\n\nAutomatisk import:"
                f"\nNye Arkade-rapporter: {auto.imported}"
                f"\nAllerede importert: {auto.already_imported}"
                f"\nPRONOM koblet: {auto.pronom_attached}"
                f"\nPRONOM uten kobling: {auto.pronom_unattached}"
                f"\nImportfeil: {auto.failed + auto.pronom_failed}"
            )
        self._progress.configure(
            text=(
                f"Arkade 5 ferdig: {summary.succeeded} CLI-kjøring(er) fullført, "
                f"{summary.failed} feil, {summary.skipped} hoppet over."
                f"{import_text}"
            )
        )
        self._run_button.configure(text="Kjørt", state="disabled")
        messagebox.showinfo(
            "Data Workflow Manager",
            (
                f"Arkade 5-kjøring ferdig.\n\nFullført teknisk: {summary.succeeded}"
                f"\nFeil: {summary.failed}\nHoppet over: {summary.skipped}"
                f"{dialog_import_text}"
            ),
            parent=self,
        )

    def _finish_error(self, message: str) -> None:
        self._stop_activity()
        self._close_button.configure(state="normal")
        self._noark_check.configure(state="normal")
        self._pronom_check.configure(state="normal")
        self._refresh_plan()
        self._progress.configure(text="Arkade 5-kjøringen kunne ikke fullføres.")
        messagebox.showerror("Data Workflow Manager", message, parent=self)
