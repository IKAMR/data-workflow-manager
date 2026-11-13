"""Human-in-the-loop experience assessment for saved standard-value findings."""
from __future__ import annotations
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QPlainTextEdit, QVBoxLayout)
from app.noark_experience_v0114_a7 import find_known_cases, save_assessment, save_local_practice
from app.noark_xsd_local_evidence_v0114_a6 import work_from_report

STATUS_LABELS = (
    ('needs_follow_up', 'Trenger videre faglig gjennomgang'),
    ('reviewed_equivalent', 'Vurdert som semantisk ekvivalent'),
    ('not_accepted', 'Vurdert som problematisk / ikke akseptert'),
)

class ExperienceAssessmentDialog(QDialog):
    def __init__(self, parent, finding, version_evidence, metadata_id):
        super().__init__(parent)
        self.setWindowTitle('Lokal erfaringsvurdering – ' + metadata_id)
        self.resize(760, 540)
        self.finding = finding
        self.version_evidence = version_evidence
        self.work = work_from_report(finding.report_path)
        version = version_evidence.version if version_evidence.status == 'confirmed' else None
        self.cases = find_known_cases(metadata_id=metadata_id, field=finding.field,
                                     noark_version=version, observed_values=finding.extra)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Kjent erfaringssak – vurderingsforslag, ikke automatisk testkonklusjon.'))
        self.info=QLabel(self)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.picker=QComboBox(self)
        for case in self.cases:
            self.picker.addItem(f"{case['case_id']} · {case['observed_value']} ({case['observed_count']} forekomster)",case['case_id'])
        layout.addWidget(self.picker)
        self.picker.currentIndexChanged.connect(self._refresh)
        self.status=QComboBox(self)
        for key,label in STATUS_LABELS:
            self.status.addItem(label,key)
        layout.addWidget(QLabel('Kontrollørens vurdering'))
        layout.addWidget(self.status)
        self.note=QPlainTextEdit(self)
        self.note.setPlaceholderText('Faglig begrunnelse og eventuelle forbehold')
        layout.addWidget(QLabel('Kontrollmerknad (kan redigeres)'))
        layout.addWidget(self.note,1)
        self.reuse=QCheckBox('Lagre merknad som lokal praksis på denne klienten (i tillegg til Work)')
        self.reuse.setToolTip('Vurderingshistorikk lagres alltid i jobbens Work. Kryss av for å gjenbruke merknaden i brukerprofilen på denne PC-en.')
        layout.addWidget(self.reuse)
        self.place=QLabel(self)
        self.place.setWordWrap(True)
        layout.addWidget(self.place)
        footer=QHBoxLayout()
        footer.addStretch(1)
        self.save=QPushButton('Lagre vurdering i Work')
        self.save.clicked.connect(self._save)
        footer.addWidget(self.save)
        close=QPushButton('Lukk')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._refresh()

    def _refresh(self,*_):
        index=self.picker.currentIndex()
        case=self.cases[index] if 0<=index<len(self.cases) else None
        if case is None:
            self.info.setText('Ingen kjent erfaringssak passer både metadatafelt, observert verdi og bekreftet uttrekksversjon. Ingen automatisk vurdering foreslås.')
            self.note.setPlainText('')
        else:
            self.info.setText(f"{case['metadata_id']} · Noark 5 v{self.version_evidence.version} · "
              f"{case['observed_value']} / {case['reference_value']} · {case['review_status']} · "
              f"lokal praksis: {'ja' if case.get('local_practice') else 'nei'}")
            self.note.setPlainText(case['suggested_note'])
        valid=case is not None and self.work is not None
        self.save.setEnabled(valid)
        self.reuse.setEnabled(valid)
        self.place.setText('Vurdering lagres i jobbens Work: '+str(self.work)+'\nAvkrysset lokal praksis lagres separat i brukerprofilen på denne klienten.' if self.work is not None else
              'Jobbens Work kan ikke identifiseres; ingen lagring er mulig.')

    def _save(self):
        index=self.picker.currentIndex()
        if not (0<=index<len(self.cases)) or self.work is None:
            return
        case=self.cases[index]
        note=self.note.toPlainText().strip()
        try:
            path=save_assessment(self.work,case_id=case['case_id'],
                noark_version=self.version_evidence.version,
                observed_value=case['observed_value'],observed_count=case['observed_count'],
                status=self.status.currentData(),note=note,test_id=self.finding.test_id,
                source=self.version_evidence.source)
            extra=''
            if self.reuse.isChecked():
                try:
                    shared=save_local_practice(case_id=case['case_id'],note=note)
                    extra='\nLokal praksis: '+str(shared)
                except (OSError,ValueError) as exc:
                    extra='\nVurderingen er lagret, men lokal praksis kunne ikke lagres: '+str(exc)
            QMessageBox.information(self,'Vurdering lagret',
                'Ny vurderingshendelse lagret i jobbens Work:\n'+str(path)+extra+
                '\n\nOpprinnelig kontrollresultat er ikke endret.')
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Kunne ikke lagre vurdering',str(exc))
