from __future__ import annotations

from pathlib import Path
import customtkinter as ctk

from noark5_workflow.core.raw_result_store import RawResultEnvelope, RawResultStore
from . import theme


def work_operations_for_job(job) -> Path | None:
    """Return the job's effective/configured Work - operations path."""
    effective = getattr(job, "_effective_work_operations", None)
    work_operations = effective or getattr(job, "work_operations", None)
    if work_operations is None:
        return None
    return Path(work_operations)


def raw_result_path_for_job(job) -> Path | None:
    """Return the active job's raw-result ledger.

    When the job-list output-subfolder rule is active, JobRunner stores its
    effective Work - operations path transiently on the job. Result views must
    use that exact path rather than the persisted base Work - operations path.
    """
    work_operations = work_operations_for_job(job)
    if work_operations is None:
        return None
    return work_operations / "wf" / "results" / "raw-results.jsonl"


def raw_results_storage_unavailable(job) -> bool:
    """True when Work is configured but currently unreachable/offline."""
    work_operations = work_operations_for_job(job)
    if work_operations is None:
        return False
    try:
        return not work_operations.exists()
    except OSError:
        return True


def raw_results_for_job(job) -> list[RawResultEnvelope]:
    """Load raw results relevant to one job from its effective work area."""
    path = raw_result_path_for_job(job)
    if path is None or not path.is_file():
        return []
    items = RawResultStore(path).results()
    job_id = str(getattr(job, "job_id", "") or "")
    extraction = getattr(job, "active_extraction_root", None)
    source_root = str(Path(extraction)) if extraction else ""
    visible: list[RawResultEnvelope] = []
    for item in items:
        if item.job_id:
            if item.job_id == job_id:
                visible.append(item)
            continue
        if source_root and item.source_root and Path(item.source_root) == Path(source_root):
            visible.append(item)
    return visible


class RawResultsDialog(ctk.CTkToplevel):
    """Read-only practical view of append-only raw results."""

    def __init__(self, master, job) -> None:
        super().__init__(master)
        self.job = job
        self.title(f"Råresultater – {job.job_id}")
        self.geometry("1500x720")
        self.minsize(1080, 520)
        self.configure(fg_color=theme.APP_BG)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text=f"RÅRESULTATER – {job.job_id}",
            font=theme.font(theme.TITLE_SIZE, "bold"),
            text_color=theme.BLUE,
        ).grid(row=0, column=0, padx=18, pady=(16, 3), sticky="w")

        self.path_label = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.path_label.grid(row=1, column=0, padx=18, pady=(0, 3), sticky="ew")

        self.summary_label = ctk.CTkLabel(
            self,
            text="",
            font=theme.font(theme.SMALL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.summary_label.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="ew")

        self.items = ctk.CTkScrollableFrame(
            self, fg_color=theme.PANEL_BG_DARK, corner_radius=8
        )
        self.items.grid(row=3, column=0, padx=18, pady=4, sticky="nsew")
        self.items.grid_columnconfigure(3, weight=1)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=18, pady=(8, 16), sticky="e")
        ctk.CTkButton(
            buttons,
            text="Oppdater",
            width=100,
            fg_color=theme.BUTTON_BG,
            hover_color=theme.BUTTON_HOVER,
            command=self.refresh,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            buttons,
            text="Lukk",
            width=90,
            fg_color=theme.BLUE_DIM,
            hover_color=theme.BLUE,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self.refresh()

    def _clear_items(self) -> None:
        for child in self.items.winfo_children():
            child.destroy()

    def _show_storage_unavailable(self, path: Path | None) -> None:
        work_operations = work_operations_for_job(self.job)

        self.summary_label.configure(
            text=(
                "Lagringsområdet for aktiv jobb er ikke tilgjengelig. "
                "Råresultatene kan derfor ikke leses."
            )
        )

        lines = [
            "LAGRING UTILGJENGELIG",
            "",
            "Lagringsområdet for aktiv jobb er ikke tilgjengelig.",
            "Koble til / lås opp lagringen og trykk Oppdater.",
        ]

        if work_operations is not None:
            lines.extend(("", "Forventet Work-bane:", str(work_operations)))

        if path is not None:
            lines.extend(("", "Forventet råresultatfil:", str(path)))

        lines.extend(
            (
                "",
                "Dette betyr ikke at jobben har 0 råresultater.",
            )
        )

        ctk.CTkLabel(
            self.items,
            text="\n".join(lines),
            font=theme.font(theme.NORMAL_SIZE),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
        ).grid(
            row=0,
            column=0,
            columnspan=5,
            padx=14,
            pady=24,
            sticky="nw",
        )

    def refresh(self) -> None:
        path = raw_result_path_for_job(self.job)
        self.path_label.configure(
            text=(
                str(path)
                if path is not None
                else "Work - operations er ikke definert"
            )
        )

        self._clear_items()

        # Important: an unreachable Work area is not evidence of zero results.
        if raw_results_storage_unavailable(self.job):
            self._show_storage_unavailable(path)
            return

        try:
            items = raw_results_for_job(self.job)
        except (OSError, ValueError) as exc:
            self.summary_label.configure(
                text=f"Kunne ikke lese råresultater: {exc}"
            )
            ctk.CTkLabel(
                self.items,
                text=(
                    "Råresultatfilen kunne ikke leses. "
                    "Dette er ikke det samme som at jobben har 0 råresultater."
                ),
                font=theme.font(theme.NORMAL_SIZE),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(
                row=0,
                column=0,
                columnspan=5,
                padx=14,
                pady=24,
                sticky="w",
            )
            return

        passed = sum(1 for item in items if item.ok)
        failed = len(items) - passed
        self.summary_label.configure(
            text=(
                f"{len(items)} råresultater for aktiv jobb – "
                f"PASS: {passed}, FAIL: {failed}. "
                "Dette er observasjoner, ikke endelig faglig vurdering eller PREMIS."
            )
        )

        headers = ("Tid", "Status", "Test/definisjon", "result_id", "Operasjon")
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self.items,
                text=text,
                font=theme.font(theme.SMALL_SIZE, "bold"),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=col, padx=8, pady=(6, 4), sticky="ew")

        if not items:
            ctk.CTkLabel(
                self.items,
                text="Ingen råresultater er lagret for denne jobben ennå.",
                font=theme.font(theme.NORMAL_SIZE),
                text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=5, padx=10, pady=28, sticky="w")
            return

        for row, item in enumerate(reversed(items), start=1):
            status = "PASS" if item.ok else "FAIL"
            test_label = item.test_id
            if item.definition_version:
                test_label = f"{test_label} [{item.definition_version}]"
            values = (
                item.recorded_at,
                status,
                test_label,
                item.result_id,
                item.operation_id,
            )
            for col, value in enumerate(values):
                ctk.CTkLabel(
                    self.items,
                    text=str(value),
                    font=theme.font(theme.SMALL_SIZE),
                    anchor="w",
                    justify="left",
                ).grid(row=row, column=col, padx=8, pady=5, sticky="ew")
