"""Qt depot organization and document-header settings, v0.2.2-a1.

The built-in Test Depot is a read-only demo. Operator-created depot profiles
are independent of app startup profiles, the signed user identity and DIAS/METS.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from app.depot_profiles_v022_a1 import (
    DOCUMENT_KINDS, DOCUMENT_LABELS, SIZES, TEST_ID, DepotProfile,
    DepotProfileError, DepotProfileSet, activate_profile, delete_profile,
    document_header_context, header_preview_html, import_logo,
    load_depot_profiles, new_profile, resolve_logo, save_depot_profiles,
    upsert_profile, validate_profile,
)

_EDITABLE = (
    ("profile_name", "Profilnavn"),
    ("organization_name", "Depot / organisasjon"),
    ("organization_number", "Organisasjonsnummer"),
    ("department", "Avdeling / enhet"),
    ("sender_name", "Avsender i dokumenter"),
    ("address", "Besøks-/postadresse"),
    ("postal_code", "Postnummer"),
    ("city", "Poststed"),
    ("country", "Land"),
    ("telephone", "Telefon"),
    ("email", "E-post"),
    ("website", "Nettsted (https://)"),
    ("signature_name", "Navn i signaturfelt"),
    ("signature_title", "Stilling i signaturfelt"),
    ("reference_prefix", "Saks-/referanseprefiks"),
    ("footer_text", "Bunntekst"),
)


class DepotProfileDialog(QDialog):
    def __init__(self, parent=None, *, path: Path | None = None):
        super().__init__(parent)
        self._path = path
        self._store = load_depot_profiles(path=path)
        self._profile = self._store.active
        self._pending_logo: Path | None = None
        self._logo_override: str | None = None
        self._selecting = False
        self.setWindowTitle("Depotprofil og dokumentoppsett")
        self.setMinimumSize(740, 570)
        self.resize(1020, 770)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)

        outer = QVBoxLayout(self)
        heading = QLabel("DEPOTPROFIL – AVSENDER OG DOKUMENTOPPSETT", self)
        heading.setStyleSheet("font-size:18px;font-weight:700;")
        outer.addWidget(heading)
        explanation = QLabel(
            "Depotidentitet er ikke DWM-brukerprofil eller Noark 5-kontrollprofil. "
            "Ingen originale arkivuttrekk eller eksisterende rapporter endres. "
            "Test Depot er en fiktiv, skrivebeskyttet demoprofil.", self,
        )
        explanation.setWordWrap(True)
        outer.addWidget(explanation)

        picker = QHBoxLayout()
        picker.addWidget(QLabel("Velg depotprofil:", self))
        self.profile_choice = QComboBox(self)
        self.profile_choice.setObjectName("v022_a1_depot_profile_choice")
        picker.addWidget(self.profile_choice, 1)
        self.copy_button = QPushButton("Ny / lag kopi…", self)
        self.copy_button.clicked.connect(self._new)
        picker.addWidget(self.copy_button)
        self.delete_button = QPushButton("Slett profil…", self)
        self.delete_button.clicked.connect(self._delete)
        picker.addWidget(self.delete_button)
        outer.addLayout(picker)

        self.tabs = QTabWidget(self)
        outer.addWidget(self.tabs, 1)
        editor = QWidget(self.tabs)
        editor_layout = QVBoxLayout(editor)
        scroll = QScrollArea(editor)
        scroll.setWidgetResizable(True)
        editor_layout.addWidget(scroll)
        form_widget = QWidget(scroll)
        form = QFormLayout(form_widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.fields: dict[str, QLineEdit] = {}
        for key, label in _EDITABLE:
            value = QLineEdit(form_widget)
            value.setObjectName("v022_a1_" + key)
            if key == "footer_text":
                value.setPlaceholderText("Valgfri bunntekst på egne depotdokumenter")
            form.addRow(label + ":", value)
            self.fields[key] = value
            value.textChanged.connect(self._preview)
        scroll.setWidget(form_widget)
        self.tabs.addTab(editor, "Depot og avsender")

        documents = QWidget(self.tabs)
        docs_layout = QVBoxLayout(documents)
        intro = QLabel("Headerstørrelse velges separat for hver dokumenttype. "
                       "Small = kompakt, Medium = organisasjon og enhet, "
                       "Full = også adresse og kontaktinformasjon.", documents)
        intro.setWordWrap(True)
        docs_layout.addWidget(intro)
        formats = QFormLayout()
        self.size_choices: dict[str, QComboBox] = {}
        for kind in DOCUMENT_KINDS:
            picker_size = QComboBox(documents)
            picker_size.setObjectName("v022_a1_header_" + kind)
            for size in SIZES:
                picker_size.addItem(size, size)
            picker_size.currentIndexChanged.connect(self._preview)
            formats.addRow(DOCUMENT_LABELS[kind] + ":", picker_size)
            self.size_choices[kind] = picker_size
        docs_layout.addLayout(formats)
        logo_row = QHBoxLayout()
        self.logo_status = QLabel(documents)
        self.logo_status.setWordWrap(True)
        logo_row.addWidget(self.logo_status, 1)
        self.logo_button = QPushButton("Velg PNG/JPEG-logo…", documents)
        self.logo_button.clicked.connect(self._pick_logo)
        logo_row.addWidget(self.logo_button)
        self.clear_logo_button = QPushButton("Fjern logo", documents)
        self.clear_logo_button.clicked.connect(self._clear_logo)
        logo_row.addWidget(self.clear_logo_button)
        docs_layout.addLayout(logo_row)
        self.logo_visual = QLabel(documents)
        self.logo_visual.setMinimumHeight(65)
        self.logo_visual.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        docs_layout.addWidget(self.logo_visual)
        docs_layout.addStretch(1)
        self.tabs.addTab(documents, "Dokumenter og logo")

        preview_page = QWidget(self.tabs)
        pv = QVBoxLayout(preview_page)
        kind_row = QHBoxLayout()
        kind_row.addWidget(QLabel("Forhåndsvis dokumenttype:", preview_page))
        self.preview_kind = QComboBox(preview_page)
        for kind in DOCUMENT_KINDS:
            self.preview_kind.addItem(DOCUMENT_LABELS[kind], kind)
        self.preview_kind.currentIndexChanged.connect(self._preview)
        kind_row.addWidget(self.preview_kind)
        kind_row.addStretch(1)
        pv.addLayout(kind_row)
        self.preview_html = QTextBrowser(preview_page)
        self.preview_html.setOpenExternalLinks(False)
        self.preview_html.setObjectName("v022_a1_depot_header_preview")
        pv.addWidget(self.preview_html, 1)
        preview_note = QLabel(
            "Forhåndsvisningen viser kun brev-/rapportheader. Eksisterende rapportmaler "
            "endres ikke automatisk i a1; samme profildata brukes i kommende sjekkliste og brev.",
            preview_page,
        )
        preview_note.setWordWrap(True)
        pv.addWidget(preview_note)
        self.tabs.addTab(preview_page, "Header – forhåndsvisning")

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                    QDialogButtonBox.StandardButton.Close, parent=self)
        controls.button(QDialogButtonBox.StandardButton.Save).setText("Lagre og bruk depotprofil")
        controls.accepted.connect(self._save)
        controls.rejected.connect(self.reject)
        outer.addWidget(controls)

        self.profile_choice.currentIndexChanged.connect(self._select)
        self._load_choices(self._profile.profile_id)

    def _load_choices(self, current: str) -> None:
        self._selecting = True
        try:
            self.profile_choice.clear()
            for profile in self._store.profiles:
                label = profile.profile_name + (" (aktiv)" if profile.profile_id == self._store.active_profile_id else "")
                self.profile_choice.addItem(label, profile.profile_id)
            if current not in [self.profile_choice.itemData(i) for i in range(self.profile_choice.count())]:
                # A newly created (not yet saved) profile is visible until Save/Close.
                self.profile_choice.addItem(self._profile.profile_name + " (ikke lagret)", current)
            self.profile_choice.setCurrentIndex(self.profile_choice.findData(current))
        finally:
            self._selecting = False
        self._show_profile()

    def _show_profile(self) -> None:
        is_demo = self._profile.is_template
        for key, field in self.fields.items():
            field.blockSignals(True)
            field.setText(str(getattr(self._profile, key)))
            field.setReadOnly(is_demo)
            field.blockSignals(False)
        for kind, picker in self.size_choices.items():
            picker.blockSignals(True)
            picker.setCurrentIndex(picker.findData(self._profile.header_sizes[kind]))
            picker.setEnabled(not is_demo)
            picker.blockSignals(False)
        self.logo_button.setEnabled(not is_demo)
        self.clear_logo_button.setEnabled(not is_demo)
        self.delete_button.setEnabled(not is_demo)
        self._preview()

    def _draft(self) -> DepotProfile:
        if self._profile.is_template:
            return self._profile
        updates = {key: field.text().strip() for key, field in self.fields.items()}
        updates["header_sizes"] = {kind: str(picker.currentData()) for kind, picker in self.size_choices.items()}
        if self._logo_override is not None:
            updates["logo_ref"] = self._logo_override
        return replace(self._profile, **updates)

    def _dirty(self) -> bool:
        if self._pending_logo is not None:
            return True
        if self._profile.profile_id not in {p.profile_id for p in self._store.profiles}:
            return True
        return self._draft() != self._profile

    def _discard_allowed(self) -> bool:
        if not self._dirty():
            return True
        answer = QMessageBox.question(
            self, "Ulagrede profilendringer",
            "Ulagrede endringer i depotprofilen vil gå tapt. Fortsette uten å lagre?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _select(self, _index: int) -> None:
        if self._selecting:
            return
        selected = str(self.profile_choice.currentData() or "")
        if selected == self._profile.profile_id:
            return
        if not self._discard_allowed():
            self._selecting = True
            self.profile_choice.setCurrentIndex(self.profile_choice.findData(self._profile.profile_id))
            self._selecting = False
            return
        self._profile = self._store.get(selected)
        self._pending_logo = None
        self._logo_override = None
        self._show_profile()

    def _new(self) -> None:
        if not self._discard_allowed():
            return
        name, accepted = QInputDialog.getText(self, "Ny depotprofil", "Navn på ny depotprofil:")
        if not accepted:
            return
        try:
            self._profile = new_profile(name=name, source=self._profile)
        except DepotProfileError as exc:
            QMessageBox.warning(self, "Ny depotprofil", str(exc))
            return
        self._pending_logo = None
        self._logo_override = None
        self._load_choices(self._profile.profile_id)
        self.tabs.setCurrentIndex(0)

    def _pick_logo(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Velg depotlogo", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg);;Alle filer (*)",
        )
        if selected:
            file = Path(selected)
            if file.is_symlink() or not file.is_file() or file.stat().st_size > 2 * 1024 * 1024:
                QMessageBox.warning(self, "Logo", "Logo må være en vanlig bildefil på høyst 2 MiB.")
                return
            self._pending_logo = file
            self._logo_override = None
            self._preview()

    def _clear_logo(self) -> None:
        self._pending_logo = None
        if not self._profile.is_template:
            self._logo_override = ""
        self._preview()

    def _preview(self, *_ignored) -> None:
        try:
            profile = self._draft()
            kind = str(self.preview_kind.currentData() or "checklist")
            context = document_header_context(profile, kind, path=self._path)
            self.preview_html.setHtml(header_preview_html(context))
        except (ValueError, OSError) as exc:
            self.preview_html.setPlainText("Header kan ikke vises: " + str(exc))
        self.status.setText(
            ("DEMO: Test Depot kan brukes eller kopieres, men ikke overskrives. "
             if self._profile.is_template else
             "Egen depotprofil – lagres kun lokalt på denne maskinens brukerområde. ")
            + ("Ulagrede endringer." if self._dirty() else
               "Aktiv profil." if self._store.active_profile_id == self._profile.profile_id else
               "Velg Lagre og bruk for å aktivere profilen.")
        )
        try:
            source = self._pending_logo or resolve_logo(self._draft(), path=self._path)
            self.logo_status.setText(source.name if source else "Standardikon TD (ingen ekstern logo)")
            if source:
                image = QPixmap(str(source))
                if image.isNull():
                    self.logo_visual.setText("Logoen kunne ikke leses som bilde.")
                    self.logo_visual.setPixmap(QPixmap())
                else:
                    self.logo_visual.setPixmap(image.scaled(250, 60,
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.logo_visual.setPixmap(QPixmap())
                self.logo_visual.setText("▣  TD – Test Depot / depotprofil")
        except (DepotProfileError, OSError) as exc:
            self.logo_visual.setText("Logofeil: " + str(exc))
            self.logo_status.setText("Logo må kontrolleres")

    def _save(self) -> None:
        try:
            if self._profile.is_template:
                updated = activate_profile(self._store, TEST_ID)
            else:
                profile = self._draft()
                if self._pending_logo is not None:
                    ref = import_logo(self._pending_logo, path=self._path)
                    profile = replace(profile, logo_ref=ref)
                validate_profile(profile)
                updated = upsert_profile(self._store, profile, activate=True)
            save_depot_profiles(updated, path=self._path)
        except (DepotProfileError, OSError) as exc:
            QMessageBox.warning(self, "Lagring av depotprofil", str(exc))
            return
        self._store = updated
        self._profile = updated.active
        self._pending_logo = None
        self._logo_override = None
        self._load_choices(self._profile.profile_id)
        self.accept()

    def _delete(self) -> None:
        if self._profile.is_template:
            return
        if self._profile.profile_id not in {p.profile_id for p in self._store.custom_profiles}:
            if not self._discard_allowed():
                return
            self._profile = self._store.active
            self._pending_logo = None
            self._load_choices(self._profile.profile_id)
            return
        answer = QMessageBox.question(
            self, "Slett depotprofil",
            "Slette bare depotprofilen (ingen Source, Work eller rapporter slettes)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            store = delete_profile(self._store, self._profile.profile_id)
            save_depot_profiles(store, path=self._path)
        except (OSError, DepotProfileError) as exc:
            QMessageBox.warning(self, "Slett depotprofil", str(exc))
            return
        self._store = store
        self._profile = store.active
        self._pending_logo = None
        self._logo_override = None
        self._load_choices(self._profile.profile_id)

    def reject(self) -> None:
        if self._discard_allowed():
            super().reject()


def install_depot_profile_controls(window) -> bool:
    """Add an explicit profile action to the established Reporting workspace."""
    if getattr(window, "_v022_a1_depot_profile_button", None) is not None:
        return True
    reporting = window.findChild(QWidget, "v020_a4_reporting_page")
    if reporting is None or reporting.layout() is None:
        return False

    strip = QHBoxLayout()
    status = QLabel(reporting)
    status.setObjectName("v022_a1_active_depot_identity")
    status.setWordWrap(True)
    strip.addWidget(status, 1)
    action = QPushButton("Depotprofil / dokumentoppsett…", reporting)
    action.setObjectName("v022_a1_open_depot_profile")
    action.setMinimumHeight(37)
    action.setToolTip("Organisasjonsprofil og dokumentheader. Ikke Noark-profil eller brukeridentitet.")
    strip.addWidget(action)
    reporting.layout().insertLayout(0, strip)

    def refresh() -> None:
        try:
            selected = load_depot_profiles().active
            status.setText("Aktiv depotprofil: " + selected.profile_name +
                           (" [DEMO]" if selected.is_template else ""))
        except (DepotProfileError, OSError) as exc:
            status.setText("Depotprofil kunne ikke leses: " + str(exc))

    def show_profile(*_ignored) -> None:
        try:
            dialog = DepotProfileDialog(window)
        except (OSError, DepotProfileError) as exc:
            QMessageBox.warning(window, "Depotprofil", str(exc))
            return
        dialog.exec()
        refresh()

    action.clicked.connect(show_profile)
    window._v022_a1_depot_profile_button = action
    window._v022_a1_depot_profile_refresh = refresh
    refresh()
    return True
