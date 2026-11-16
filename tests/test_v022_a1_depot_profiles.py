"""v0.2.2-a1: real depot identity, local persistence, branding and Qt navigation."""
from __future__ import annotations

import ast
import base64
from dataclasses import asdict, replace
from pathlib import Path
import json
import re
import tempfile
import unittest

from app.depot_profiles_v022_a1 import (
    DEFAULT_SIZES, DOCUMENT_KINDS, FILE_TYPE, TEST_DEPOT, TEST_ID,
    DepotProfileError, DepotProfileSet, activate_profile, delete_profile,
    depot_profiles_path, document_header_context, header_preview_html, import_logo,
    load_depot_profiles, new_profile, resolve_logo, save_depot_profiles, upsert_profile,
    validate_profile,
)

ROOT = Path(__file__).resolve().parents[1]
# Real, small PNG image with a 1x1 pixel; never modifies the imported source.
def _chunk(kind: bytes, payload: bytes) -> bytes:
    import struct
    import zlib
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload)))


def _tiny_png() -> bytes:
    import struct
    import zlib
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    rgb = zlib.compress(b"\x00\xff\xff\xff")
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", rgb) + _chunk(b"IEND", b""))


SMALL_PNG = _tiny_png()


class A1DepotProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "user-depot-profiles.json"

    def _new(self, name="Fylkesdepotet"):
        return new_profile(name=name)

    def test_builtin_demo_is_readonly_and_separate_from_login_or_noark(self):
        store = load_depot_profiles(path=self.path)
        self.assertFalse(self.path.exists())
        self.assertEqual(store.active_profile_id, TEST_ID)
        self.assertTrue(store.active.is_template)
        self.assertEqual(store.active.organization_name, "Test Depot")
        self.assertIn("DEMO", store.active.footer_text)
        self.assertTrue(store.active.email.endswith(".invalid"))
        self.assertEqual(len(store.profiles), 1)
        with self.assertRaises(DepotProfileError):
            validate_profile(replace(TEST_DEPOT, organization_name="Real depot"))
        with self.assertRaises(DepotProfileError):
            upsert_profile(store, TEST_DEPOT)
        with self.assertRaises(DepotProfileError):
            delete_profile(store, TEST_ID)

    def test_create_activate_and_preserve_user_organization_details(self):
        profile = self._new()
        profile = replace(
            profile, organization_name="Kystarkivet", organization_number="123456789",
            department="Digitalt depot", sender_name="Kystarkivet – depot",
            address="Fjordvegen 14", postal_code="6000", city="Fjordvik",
            telephone="70 00 00 00", email="post@example.org",
            website="https://example.org", signature_name="Arkivmedarbeider",
            signature_title="Depotansvarlig", reference_prefix="SAK-",
            footer_text="Fiktivt depot",
            header_sizes={"checklist": "Small", "quality_report": "Medium",
                          "depot_report": "Full", "approval_letter": "Full"},
        )
        store = upsert_profile(DepotProfileSet(), profile)
        self.assertEqual(store.active.profile_id, profile.profile_id)
        save_depot_profiles(store, path=self.path)
        loaded = load_depot_profiles(path=self.path)
        self.assertEqual(loaded, store)
        self.assertNotEqual(loaded.active.profile_id, TEST_ID)
        self.assertEqual(loaded.get(profile.profile_id).email, "post@example.org")
        self.assertEqual(json.loads(self.path.read_text(encoding='utf8'))["file_type"], FILE_TYPE)
        self.assertEqual(loaded.get(TEST_ID), TEST_DEPOT)

    def test_many_profiles_remain_independent_and_builtin_remains_available(self):
        a = replace(self._new("Depot A"), organization_name="Arkivdepot A")
        b = replace(self._new("Depot B"), organization_name="Arkivdepot B")
        first = upsert_profile(DepotProfileSet(), a)
        both = upsert_profile(first, b)
        self.assertEqual(len(both.profiles), 3)
        chosen = activate_profile(both, a.profile_id)
        save_depot_profiles(chosen, path=self.path)
        self.assertEqual(load_depot_profiles(path=self.path).active.organization_name, "Arkivdepot A")
        self.assertEqual(load_depot_profiles(path=self.path).get(b.profile_id).organization_name, "Arkivdepot B")
        remaining = delete_profile(chosen, a.profile_id)
        self.assertEqual(remaining.active_profile_id, TEST_ID)
        self.assertEqual(len(remaining.custom_profiles), 1)
        self.assertEqual(remaining.custom_profiles[0].profile_id, b.profile_id)

    def test_profile_validation_rejects_bad_identity_and_bad_fields(self):
        p = self._new()
        bad = (
            replace(p, organization_name=""),
            replace(p, profile_name="\n"),
            replace(p, profile_name="Line\nbreak"),
            replace(p, organization_number="123"),
            replace(p, email="not-an-email"),
            replace(p, website="javascript:alert(1)"),
            replace(p, logo_ref="../../source/info.xml"),
            replace(p, header_sizes={"checklist": "XL"}),
            replace(p, header_sizes={**DEFAULT_SIZES, "approval_letter": "Gigantisk"}),
        )
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(DepotProfileError):
                    validate_profile(item)
        with self.assertRaises(DepotProfileError):
            activate_profile(DepotProfileSet(), "missing")

    def test_invalid_existing_store_is_never_silently_replaced(self):
        self.path.write_text("{not json", encoding="utf8")
        before = self.path.read_bytes()
        with self.assertRaises(DepotProfileError):
            load_depot_profiles(path=self.path)
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(DepotProfileError):
            load_depot_profiles(path=self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_stale_profile_and_format_are_not_accidentally_loaded(self):
        for raw in ({"file_type": "wrong", "format_version": 1, "profiles": []},
                    {"file_type": FILE_TYPE, "format_version": 999, "profiles": []},
                    {"file_type": FILE_TYPE, "format_version": 1, "active_profile_id": "missing", "profiles": []},
                    {"file_type": FILE_TYPE, "format_version": 1, "active_profile_id": TEST_ID, "profiles": [asdict(TEST_DEPOT)]}):
            with self.subTest(raw=raw):
                self.path.write_text(json.dumps(raw), encoding="utf8")
                with self.assertRaises(DepotProfileError):
                    load_depot_profiles(path=self.path)

    def test_atomic_save_and_no_work_or_source_dependency(self):
        saved = save_depot_profiles(DepotProfileSet(), path=self.path)
        self.assertEqual(saved, self.path)
        self.assertEqual(len(list(self.root.glob('.depot-profile-*.tmp'))), 0)
        self.assertEqual(load_depot_profiles(path=self.path).active, TEST_DEPOT)
        # The default path uses the same per-user root as the existing user profile,
        # but is a distinct file rather than changing the user's login identity.
        from app.user_profile import profile_path, user_data_dir
        self.assertEqual(depot_profiles_path().parent, user_data_dir())
        self.assertNotEqual(depot_profiles_path(), profile_path())
        self.assertNotIn("work", depot_profiles_path().name.lower())

    def test_logo_copy_is_content_addressed_and_source_is_untouched(self):
        image = self.root / "source.png"
        image.write_bytes(SMALL_PNG)
        original = image.read_bytes()
        ref = import_logo(image, path=self.path)
        self.assertRegex(ref, r'^assets/[0-9a-f]{64}\.png$')
        depot = replace(self._new(), logo_ref=ref)
        asset = resolve_logo(depot, path=self.path)
        self.assertEqual(asset.read_bytes(), original)
        self.assertEqual(image.read_bytes(), original)
        self.assertEqual(import_logo(image, path=self.path), ref)
        content = document_header_context(depot, 'checklist', path=self.path)
        self.assertEqual(content['logo_ref'], ref)
        self.assertEqual(content['logo_sha256'], asset.stem)
        asset.write_bytes(original + b'changed')
        with self.assertRaises(DepotProfileError):
            document_header_context(depot, 'checklist', path=self.path)

    def test_invalid_or_oversize_logo_is_rejected(self):
        bad = self.root / "bad.png"
        bad.write_bytes(b"<?xml?><metadata/>")
        with self.assertRaises(DepotProfileError):
            import_logo(bad, path=self.path)
        bad.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with self.assertRaises(DepotProfileError):
            import_logo(bad, path=self.path)

    def test_logo_path_traversal_cannot_read_external_files(self):
        with self.assertRaises(DepotProfileError):
            resolve_logo(replace(self._new(), logo_ref="../archive.xml"), path=self.path)
        with self.assertRaises(DepotProfileError):
            validate_profile(replace(self._new(), logo_ref="C:/private/example.png"))

    def test_all_document_types_have_independent_header_size(self):
        sizes = {"checklist": "Small", "quality_report": "Medium",
                 "depot_report": "Full", "approval_letter": "Small"}
        p = replace(self._new(), header_sizes=sizes)
        seen = {kind: document_header_context(p, kind, path=self.path)["header_size"]
                for kind in DOCUMENT_KINDS}
        self.assertEqual(seen, sizes)
        context = document_header_context(p, "quality_report", path=self.path)
        self.assertEqual(context["source_type"], "local_depot_organization_profile_not_archive_metadata")
        self.assertFalse(context["automatic_approval"])
        self.assertEqual(len(context['profile_sha256']), 64)
        with self.assertRaises(DepotProfileError):
            document_header_context(p, "unknown", path=self.path)

    def test_header_preview_escapes_operator_values(self):
        p = replace(self._new(), organization_name='<img src=x onerror=alert(1)>',
                    department='Research & Data', header_sizes={**DEFAULT_SIZES, 'depot_report': 'Full'})
        ctx = document_header_context(p, 'depot_report', path=self.path)
        html = header_preview_html(ctx)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn('&lt;img', html)
        self.assertIn('Research &amp; Data', html)
        self.assertIn('not_archive_metadata', str(ctx))

    def test_header_does_not_derive_identity_from_noark_or_work(self):
        p = replace(self._new(), organization_name='Fiktivt Testarkiv')
        ctx = document_header_context(p, 'approval_letter', path=self.path)
        self.assertEqual(ctx['organization_name'], 'Fiktivt Testarkiv')
        self.assertFalse(ctx['automatic_approval'])
        self.assertNotIn('arkivskaper', ctx)
        self.assertNotIn('archive_creator', ctx)
        self.assertNotIn('noark_version', ctx)


class A1QtIntegrationContract(unittest.TestCase):
    def test_existing_entry_point_and_result_center_are_preserved(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf8')
        ast.parse(entry)
        self.assertIn('from gui_qt.main_v020_a6 import DwmMainWindow', entry)
        self.assertIn('install_integrated_home(window)', entry)
        self.assertIn('install_depot_profile_controls(window)', entry)
        self.assertLess(entry.index('install_integrated_home(window)'), entry.index('install_depot_profile_controls(window)'))
        self.assertIn('install_dropdown_positioning(application, window)', entry)

    def test_editor_uses_existing_reporting_page_not_a_second_job_engine(self):
        source = (ROOT / 'gui_qt/depot_profile_v022_a1.py').read_text(encoding='utf8')
        ast.parse(source)
        self.assertIn('v020_a4_reporting_page', source)
        self.assertIn('QPushButton("Depotprofil / dokumentoppsett…"', source)
        self.assertIn('load_depot_profiles()', source)
        self.assertIn('save_depot_profiles(updated', source)
        self.assertNotIn('record_depot_review(', source)
        self.assertNotIn('read_meta_from_mets(', source)
        self.assertNotIn('setCurrentWidget(', source)


if __name__ == '__main__':
    unittest.main()
