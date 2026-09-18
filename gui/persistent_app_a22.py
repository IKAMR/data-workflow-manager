from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from version import APP_NAME
from settings import save_config
from noark5_workflow.core.result_invalidation import (
    current_stale_operation_ids,
    mark_downstream_stale,
    mark_regenerated,
)
from noark5_workflow.core.result_selection import (
    choose_new_as_current,
    keep_previous_current,
    latest_new_result,
    operation_results,
)
from . import theme
from .info_panel import InfoPanel
from .result_versions_dialog import ResultVersionsDialog
from .workflow_status import operation_status_key
from .persistent_app_a21 import WorkflowApp as A21WorkflowApp


class WorkflowApp(A21WorkflowApp):
    """a13.3: selective re-run, version choice and downstream invalidation."""

    def __init__(self) -> None:
        self._selective_rerun_running = False
        super().__init__()
        self.workflow_panel.on_rerun = self._rerun_selected_operation
        self.workflow_panel.stale_ids_provider = self._stale_operation_ids
        self.workflow_panel.status_provider = self._operation_status_key
        self.workflow_panel.on_status_click = self._open_result_versions
        self.workflow_panel.on_regenerate_stale = self._regenerate_stale_results
        self._install_info_panel()
        self.workflow_panel.refresh()


    def _open_result_versions(self, operation_id: str) -> None:
        """Open append-only result-version history for one stable operation id."""
        job = self.current_job
        if job is None or operation_id not in job.workflow_ids:
            messagebox.showwarning(APP_NAME, "Åpne en jobb før resultatversjoner vises.")
            return
        try:
            name = self.registry.get(operation_id).definition.name
        except Exception:
            name = operation_id
        ResultVersionsDialog(self, job, operation_id, name)

    def _operation_status_key(self, operation_id: str) -> str:
        return operation_status_key(
            self.current_job, operation_id, self._stale_operation_ids()
        )

    def _install_info_panel(self) -> None:
        """Install a collapsible general-purpose information surface on the right."""
        self.grid_columnconfigure(2, weight=0)
        try:
            self.status_bar.grid_configure(columnspan=3)
        except Exception:
            pass

        self.info_panel = InfoPanel(self, on_close=self._hide_info_panel)
        self.info_panel.grid(row=1, column=2, padx=(0, 10), pady=4, sticky="nsew")

        # Reuse the established header rather than creating a second top bar.
        header = None
        for candidate in self.grid_slaves(row=0):
            if isinstance(candidate, ctk.CTkFrame):
                header = candidate
                break
        if header is not None:
            try:
                header.grid_configure(columnspan=3)
            except Exception:
                pass
            self.info_toggle_button = ctk.CTkButton(
                header,
                text="ⓘ",
                width=34,
                height=28,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                fg_color=theme.BUTTON_BG,
                hover_color=theme.BUTTON_HOVER,
                command=self._toggle_info_panel,
            )
            self.info_toggle_button.grid(row=0, column=10, padx=(2, 10), pady=8)

        self.bind("<F9>", lambda _event: self._toggle_info_panel(), add="+")
        if not bool(self.settings.get("info_panel_visible", False)):
            self.info_panel.grid_remove()

    def _set_info_panel_visible(self, visible: bool) -> None:
        if visible:
            self.info_panel.grid()
        else:
            self.info_panel.grid_remove()
        self.settings["info_panel_visible"] = bool(visible)
        try:
            save_config({"info_panel_visible": bool(visible)})
        except Exception:
            pass

    def _toggle_info_panel(self) -> None:
        try:
            visible = bool(self.info_panel.winfo_ismapped())
        except Exception:
            visible = False
        self._set_info_panel_visible(not visible)

    def _hide_info_panel(self) -> None:
        self._set_info_panel_visible(False)

    def _stale_operation_ids(self) -> set[str]:
        if self.current_job is None:
            return set()
        try:
            return set(current_stale_operation_ids(self.current_job))
        except Exception:
            return set()

    def _regenerate_stale_results(self) -> None:
        if self.batch_running or self._selective_rerun_running:
            messagebox.showwarning(APP_NAME, "En kjøring er allerede aktiv.")
            return
        job = self.current_job
        if job is None:
            messagebox.showwarning(APP_NAME, "Åpne en jobb før foreldede resultater regenereres.")
            return
        stale_ids = current_stale_operation_ids(job)
        if not stale_ids:
            messagebox.showinfo(APP_NAME, f"{job.job_id}\n\nIngen avledede resultater er markert som foreldet.")
            self.workflow_panel.refresh()
            return
        source = job.active_extraction_root
        if source is None or not Path(source).is_dir():
            messagebox.showwarning(
                APP_NAME,
                "Source er ikke tilgjengelig. Kontroller ekstern disk, nettverksstasjon "
                "eller annen lagring før foreldede resultater regenereres.",
            )
            return

        # Preserve workflow order, while freshness identity remains operation_id.
        ordered = [oid for oid in job.workflow_ids if oid in set(stale_ids)]
        labels = []
        for operation_id in ordered:
            try:
                labels.append(self.registry.get(operation_id).definition.name)
            except Exception:
                labels.append(operation_id)
        if not messagebox.askyesno(
            APP_NAME,
            f"{job.job_id}\n\n"
            "Følgende avledede resultater er foreldet og kjøres på nytt i "
            "workflow-rekkefølge:\n\n"
            + "\n".join(f"- {label}" for label in labels)
            + "\n\nEksisterende resultater og invalidasjonshistorikk slettes ikke. "
            "Bare vellykket regenererte operasjoner markeres som oppdatert.\n\n"
            "Regenerere foreldede resultater?",
        ):
            return

        self._selective_rerun_running = True
        self.cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        self.workflow_panel.regenerate_stale_button.configure(state="disabled")
        self.status_bar.set_status(
            f"Regenererer {len(ordered)} foreldede resultat(er) for {job.job_id}"
        )

        def worker() -> None:
            completed = []
            failed = None
            for operation_id in ordered:
                if self.cancel_requested:
                    failed = operation_id
                    break
                try:
                    operation = self.registry.get(operation_id)
                    name = operation.definition.name
                except Exception:
                    name = operation_id
                self._job_log(job, f"REGENERER FORELDET: {name} [{operation_id}]")
                outcome = self.job_runner.run_operation(
                    job,
                    operation_id,
                    progress_cb=lambda value, message: self._progress_callback_for_job(
                        job, value, message
                    ),
                    log_cb=lambda message: self._job_log(job, message),
                    cancelled_cb=lambda: self.cancel_requested,
                    state_cb=self._runner_state_changed,
                )
                if not outcome.ok:
                    failed = operation_id
                    self._job_log(job, f"REGENERERING FEILET: {operation_id}")
                    break
                mark_regenerated(job, operation_id)
                completed.append(operation_id)
                self._job_log(job, f"REGENERERT OG OPPDATERT: {operation_id}")

            if self.job_list_path is not None:
                self._write_job_list(self.job_list_path)
            self._selective_rerun_running = False
            remaining = current_stale_operation_ids(job)
            if failed is None:
                final = f"Regenerering fullført: {len(completed)} resultat(er) oppdatert"
            else:
                final = (
                    f"Regenerering stoppet: {len(completed)} oppdatert, "
                    f"{len(remaining)} fortsatt foreldet"
                )
            self.after(0, lambda f=final: self.status_bar.set_status(f))
            self.after(0, lambda: self.workflow_panel.run_button.configure(state="normal"))
            self.after(0, self.workflow_panel.refresh)
            self.after(0, self._update_run_button)
            self.after(0, self._refresh_jobs_window_safe)

        threading.Thread(
            target=worker,
            daemon=True,
            name="n5wfman-regenerate-stale",
        ).start()

    def _rerun_selected_operation(self, operation_id: str) -> None:
        if self.batch_running or self._selective_rerun_running:
            messagebox.showwarning(APP_NAME, "En kjøring er allerede aktiv.")
            return
        job = self.current_job
        if job is None:
            messagebox.showwarning(APP_NAME, "Åpne en jobb før en operasjon kjøres på nytt.")
            return
        if operation_id not in job.workflow_ids:
            messagebox.showwarning(APP_NAME, "Operasjonen finnes ikke i aktiv jobb.")
            return

        source = job.active_extraction_root
        if source is None or not Path(source).is_dir():
            messagebox.showwarning(
                APP_NAME,
                "Source er ikke tilgjengelig. Kontroller ekstern disk, nettverksstasjon "
                "eller annen lagring før operasjonen kjøres på nytt.",
            )
            return

        position = job.workflow_ids.index(operation_id) + 1
        total = len(job.workflow_ids)
        operation = self.registry.get(operation_id)
        name = operation.definition.name
        if not messagebox.askyesno(
            APP_NAME,
            f"{job.job_id}\n\n"
            f"Kjør bare operasjon {position} av {total} på nytt:\n{name}\n\n"
            f"Stabil operasjons-ID: {operation_id}\n\n"
            "Workflowens fullført-/cursorstatus endres ikke. Nye råresultater lagres "
            "med ny result_id, mens tidligere råresultater beholdes.\n\n"
            "Kjøre valgt operasjon på nytt?",
        ):
            return

        known_result_ids = {item.result_id for item in operation_results(job, operation_id)}

        self._selective_rerun_running = True
        self.cancel_requested = False
        self.workflow_panel.run_button.configure(state="disabled")
        self.status_bar.set_status(
            f"Selektiv gjenkjøring: {job.job_id} - operasjon {position} av {total}"
        )

        def worker() -> None:
            outcome = self.job_runner.run_operation(
                job,
                operation_id,
                progress_cb=lambda value, message: self._progress_callback_for_job(
                    job, value, message
                ),
                log_cb=lambda message: self._job_log(job, message),
                cancelled_cb=lambda: self.cancel_requested,
                state_cb=self._runner_state_changed,
            )
            if outcome.persist_recommended and self.job_list_path is not None:
                self._write_job_list(self.job_list_path)

            candidate = (
                latest_new_result(
                    job,
                    operation_id,
                    known_result_ids=known_result_ids,
                )
                if outcome.ok
                else None
            )

            final = (
                f"Selektiv gjenkjøring fullført: {name}"
                if outcome.ok
                else f"Selektiv gjenkjøring feilet: {name}"
            )
            self._selective_rerun_running = False
            self.after(0, lambda: self.status_bar.set_status(final))
            if candidate is not None:
                self.after(
                    0,
                    lambda c=candidate, oid=operation_id, n=name: self._choose_result_version(
                        oid, n, c.result_id
                    ),
                )
            self.after(0, lambda: self.workflow_panel.run_button.configure(state="normal"))
            self.after(0, self._update_run_button)
            self.after(0, self._refresh_jobs_window_safe)

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"n5wfman-selective-{operation_id}",
        ).start()

    def _choose_result_version(self, operation_id: str, name: str, candidate_result_id: str) -> None:
        job = self.current_job
        if job is None or operation_id not in job.workflow_ids:
            return

        actor = str(self.settings.get("_current_username", "") or "")
        use_new = messagebox.askyesno(
            APP_NAME,
            f"{job.job_id}\n\n"
            f"Ny resultatversjon er lagret for:\n{name}\n\n"
            "Vil du gjøre den nye kjøringen til gjeldende resultat?\n\n"
            "Ja: Ny versjon blir gjeldende. Tidligere gjeldende versjon beholdes "
            "i historikken og markeres som erstattet.\n\n"
            "Nei: Tidligere gjeldende versjon beholdes. Den nye kjøringen lagres "
            "som alternativ resultatversjon for senere vurdering.",
        )
        try:
            if use_new:
                choice = choose_new_as_current(
                    job, operation_id, candidate_result_id, actor=actor
                )
                old_id = choice.current.result_id if choice.current is not None else "ingen"
                self._job_log(
                    job,
                    f"RESULTATVERSJON GJELDENDE: {candidate_result_id} "
                    f"[{operation_id}] - tidligere={old_id}",
                )
                stale_ids = mark_downstream_stale(job, operation_id, candidate_result_id)
                if stale_ids:
                    labels = []
                    for stale_id in stale_ids:
                        try:
                            labels.append(self.registry.get(stale_id).definition.name)
                        except Exception:
                            labels.append(stale_id)
                    self._job_log(
                        job,
                        "AVLEDEDE RESULTATER FORELDET: " + ", ".join(stale_ids),
                    )
                    messagebox.showinfo(
                        APP_NAME,
                        f"{job.job_id}\n\n"
                        "Ny resultatversjon er gjort gjeldende. Følgende avledede "
                        "resultater er nå markert som foreldet og må regenereres:\n\n"
                        + "\n".join(f"- {label}" for label in labels)
                        + "\n\nEksisterende filer slettes ikke; historikken beholdes.",
                    )
                    self.status_bar.set_status(
                        f"Ny resultatversjon er gjeldende; {len(stale_ids)} avledede resultat(er) må regenereres"
                    )
                    self.workflow_panel.refresh()
                else:
                    self.status_bar.set_status(f"Ny resultatversjon er gjeldende: {name}")
                    self.workflow_panel.refresh()
            else:
                choice = keep_previous_current(
                    job, operation_id, candidate_result_id, actor=actor
                )
                old_id = choice.current.result_id if choice.current is not None else "ingen"
                self._job_log(
                    job,
                    f"RESULTATVERSJON BEHOLDT SOM ALTERNATIV: {candidate_result_id} "
                    f"[{operation_id}] - gjeldende={old_id}",
                )
                self.status_bar.set_status(f"Tidligere resultat beholdt som gjeldende: {name}")
        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                "Resultatet ble kjørt og lagret, men valg av gjeldende "
                f"resultatversjon kunne ikke registreres.\n\n{exc}",
            )



def run_gui() -> None:
    theme.apply_theme()
    app = WorkflowApp()
    app.mainloop()
