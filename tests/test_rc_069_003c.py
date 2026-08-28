"""
tests/test_rc_069_003c.py — RC-069-003C: Final Third-Party License Closure

Focused checks that the specific items RC-069-003B left open (Qt/PySide6
LGPL-3.0 full text, OpenSSL provenance, SDL2 helper/codec library
licenses, and the public portable-layout doc placement) are actually
closed in the repository and in the packaging spec. Like
test_rc_069_003b.py, these are presence/structure checks, not proof of
legal compliance — they confirm the artifacts exist and read as
"resolved" rather than "reference-only"/"NEEDS VERIFICATION", not that
a lawyer has signed off.

Covers:
1.  Qt/PySide6 LGPL file contains the full LGPLv3 text (not the old
    reference-only placeholder) and the incorporated GPLv3 text.
2.  Qt/PySide6 LGPL file no longer carries an ACTION REQUIRED marker.
3.  OpenSSL license file exists with real Apache-2.0 grant text.
4.  THIRD_PARTY_NOTICES documents both OpenSSL DLL pairs with their
    traced provenance (not "not conclusively traced").
5.  All 10 newly-added SDL2 helper/codec license files exist and are
    non-trivial.
6.  THIRD_PARTY_NOTICES no longer contains a residual
    "NEEDS VERIFICATION" marker for the components this cut closed.
7.  packaging/toroidamp.spec copies the release docs to the top-level
    dist folder (public portable layout), in addition to the existing
    _internal/ collection.
8.  All required license files (RC-069-003B + RC-069-003C) are present
    per the combined REQUIRED_LICENSE_FILES list.
"""

import unittest
from pathlib import Path

from tests.test_rc_069_003b import REQUIRED_LICENSE_FILES

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSES_DIR = REPO_ROOT / "licenses"
NOTICES_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
SPEC_PATH = REPO_ROOT / "packaging" / "toroidamp.spec"

NEW_SDL_HELPER_FILES = [
    "FreeType-FTL.txt",
    "libpng.txt",
    "libjpeg-IJG-and-BSD.txt",
    "libtiff.txt",
    "libwebp-BSD-3-Clause.txt",
    "libogg-BSD-3-Clause.txt",
    "libopus-and-opusfile-BSD.txt",
    "WavPack-BSD-3-Clause.txt",
    "PortMidi.txt",
]


def _read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestRC069003CFinalLicenseClosure(unittest.TestCase):

    def setUp(self):
        self.notices_text = _read(NOTICES_PATH)
        self.spec_text = _read(SPEC_PATH)
        self.qt_license_text = _read(LICENSES_DIR / "Qt-PySide6-LGPL-3.0.txt")
        self.openssl_license_text = _read(LICENSES_DIR / "OpenSSL-Apache-2.0.txt")

    # -- 1: Qt/PySide6 full LGPLv3 + GPLv3 text present -------------------------

    def test_01_qt_license_contains_full_lgpl_and_gpl_text(self):
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", self.qt_license_text)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", self.qt_license_text)
        self.assertIn("END OF TERMS AND CONDITIONS", self.qt_license_text)
        self.assertIn("15. Disclaimer of Warranty.", self.qt_license_text)

    # -- 2: no leftover ACTION REQUIRED marker on the Qt license file -----------

    def test_02_qt_license_no_longer_action_required(self):
        self.assertNotIn("STATUS: ACTION REQUIRED", self.qt_license_text)
        self.assertIn("STATUS: READY", self.qt_license_text)

    # -- 3: OpenSSL license file has real Apache-2.0 text ------------------------

    def test_03_openssl_license_has_apache_grant(self):
        self.assertTrue((LICENSES_DIR / "OpenSSL-Apache-2.0.txt").is_file())
        self.assertIn("Apache License", self.openssl_license_text)
        self.assertIn("Version 2.0, January 2004", self.openssl_license_text)
        self.assertIn("END OF TERMS AND CONDITIONS", self.openssl_license_text)

    # -- 4: THIRD_PARTY_NOTICES documents traced OpenSSL provenance -------------

    def test_04_notices_documents_openssl_provenance(self):
        self.assertIn("libcrypto-3.dll", self.notices_text)
        self.assertIn("libcrypto-3-x64.dll", self.notices_text)
        self.assertIn("Python314", self.notices_text)
        self.assertIn("Git for Windows", self.notices_text)

    # -- 5: new SDL2 helper/codec license files exist and are substantive -------

    def test_05_sdl_helper_license_files_present(self):
        for fname in NEW_SDL_HELPER_FILES:
            with self.subTest(fname=fname):
                path = LICENSES_DIR / fname
                self.assertTrue(path.is_file(), f"licenses/{fname} must exist")
                self.assertGreater(
                    len(path.read_text(encoding="utf-8", errors="replace")), 200
                )

    # -- 6: no residual NEEDS VERIFICATION marker in THIRD_PARTY_NOTICES --------

    def test_06_notices_has_no_residual_needs_verification(self):
        self.assertNotIn("NEEDS VERIFICATION", self.notices_text)

    # -- 7: spec copies release docs to the top-level dist folder ---------------

    def test_07_spec_public_portable_layout(self):
        self.assertIn("_PUBLIC_LAYOUT_DOCS", self.spec_text)
        self.assertIn("_DIST_ROOT", self.spec_text)
        self.assertIn("shutil.copy2", self.spec_text)
        self.assertIn("shutil.copytree", self.spec_text)

    # -- 8: full combined required-license-file list is present -----------------

    def test_08_all_required_license_files_present(self):
        for fname in REQUIRED_LICENSE_FILES:
            with self.subTest(fname=fname):
                self.assertTrue((LICENSES_DIR / fname).is_file())


if __name__ == "__main__":
    unittest.main()
