"""Temporary a15 configuration dialog for local analysis resources.

Use: python tools/configure_analysis_a15.py
The settings are retained by DWM; concurrency is not activated prematurely.
"""
from __future__ import annotations

import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analysis_resources_a15 import resource_plan, validate_resource_settings
from settings import load_config, save_config


FIELDS = (
    ('noark5_xpath_workers', 'XPath-arbeidere (0=auto)'),
    ('document_analysis_workers', 'Dokumentanalyse-arbeidere (0=auto)'),
    ('xpath_timeout_minutes', 'Tidsgrense XPath i minutter (0=ingen)'),
    ('document_timeout_minutes', 'Tidsgrense dokumentanalyse (0=ingen)'),
)


def main() -> None:
    settings = load_config()
    plan = resource_plan(settings)
    root = tk.Tk()
    root.title('DWM a15 - Ressurser for analyse')
    root.geometry('640x360')
    root.columnconfigure(1, weight=1)
    ttk.Label(root, text=f'CPU: {plan.cpu_count}  |  RAM: {plan.memory_gib or "ukjent"} GiB').grid(
        row=0, column=0, columnspan=2, padx=18, pady=15, sticky='w')
    vars_ = {}
    for i, (key, label) in enumerate(FIELDS, start=1):
        ttk.Label(root, text=label).grid(row=i, column=0, padx=18, pady=5, sticky='w')
        v = tk.StringVar(value=str(settings.get(key, 0)))
        ttk.Entry(root, textvariable=v, width=12).grid(row=i, column=1, padx=12, sticky='w')
        vars_[key] = v
    ttk.Label(root, text=('Obs: a15.1 lagrer innstillingene, men starter IKKE parallelle '
        'XPath- eller Arkade 5-prosesser. Automatisk verdi = 1 inntil '
        'motorene er testet for delte filer og uavhengige resultater.'),
        wraplength=590).grid(row=5, column=0, columnspan=2, padx=18, pady=18, sticky='w')

    def save() -> None:
        try:
            values = validate_resource_settings({k: v.get() for k, v in vars_.items()})
        except ValueError as exc:
            messagebox.showerror('Ugyldig verdi', str(exc), parent=root)
            return
        save_config(values)
        messagebox.showinfo('Lagret', 'Ressursparametrene er lagret i DWM-oppsettet.', parent=root)
        root.destroy()
    ttk.Button(root, text='Lagre', command=save).grid(row=6, column=1, padx=18, pady=10, sticky='e')
    root.mainloop()


if __name__ == '__main__':
    main()
