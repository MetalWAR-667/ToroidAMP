"""
tests/test_rc_069_003b.py — RC-069-003B: LICENSE, Third-Party Notices & User
Documentation Closure

These validate the presence/structure CONTRACT of the release documentation
set (LICENSE, THIRD_PARTY_NOTICES.md, licenses/, README links, HOWTOUSE.md,
CHANGELOG.md, and the packaging spec's inclusion of them) — not a substitute
for actual human legal review. Presence checks prove the files exist and are
internally structured as expected; they do not prove legal correctness or
completeness. See docs/release/RC_069_003B_license_and_docs.md for the
underlying audit trail.

Covers:
1.  LICENSE contains the canonical MIT grant text.
2.  THIRD_PARTY_NOTICES.md exists and is non-trivial.
3.  licenses/ directory exists with the expected core license files.
4.  README references MIT / links LICENSE.
5.  README links HOWTOUSE.md.
6.  README links CHANGELOG.md.
7.  README links THIRD_PARTY_NOTICES.md.
8.  HOWTOUSE.md contains a Validation / Self-Test Checklist section.
9.  CHANGELOG.md contains an [Unreleased] pre-release structure.
10. packaging/toroidamp.spec collects the release docs into the frozen build.
11. pyproject.toml declares the MIT license expression without a redundant/
    conflicting classifier (the exact regression that broke `pip install -e .`
    during this cut).
12. Known-required license text files are present and non-empty.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSE_PATH = REPO_ROOT / "LICENSE"
NOTICES_PATH = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
LICENSES_DIR = REPO_ROOT / "licenses"
README_PATH = REPO_ROOT / "README.md"
HOWTOUSE_PATH = REPO_ROOT / "HOWTOUSE.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SPEC_PATH = REPO_ROOT / "packaging" / "toroidamp.spec"

REQUIRED_LICENSE_FILES = [
    "Python.txt",
    "NumPy.txt",
    "pygame-ce-LGPL-2.1.txt",
    "libsndfile-LGPL-2.1.txt",
    "sounddevice-python.txt",
    "PortAudio.txt",
    "soundfile-python.txt",
    "libxmp.txt",
    "pyttsx3.txt",
    "pywin32.txt",
    "comtypes.txt",
    "SDL2.txt",
    "Quantum-font-OFL-1.1.txt",
    "Qt-PySide6-LGPL-3.0.txt",
    "PyInstaller-BUILD-TOOL-ONLY.txt",
]


def _read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TestRC069003BReleaseDocs(unittest.TestCase):

    def setUp(self):
        self.license_text = _read(LICENSE_PATH)
        self.notices_text = _read(NOTICES_PATH)
        self.readme_text = _read(README_PATH)
        self.howtouse_text = _read(HOWTOUSE_PATH)
        self.changelog_text = _read(CHANGELOG_PATH)
        self.pyproject_text = _read(PYPROJECT_PATH)
        self.spec_text = _read(SPEC_PATH)

    # -- 1: LICENSE contains the canonical MIT grant -----------------------

    def test_01_license_contains_canonical_mit_grant(self):
        self.assertTrue(LICENSE_PATH.is_file(), "LICENSE must exist")
        self.assertIn("MIT License", self.license_text)
        self.assertIn(
            "Permission is hereby granted, free of charge, to any person obtaining a copy",
            self.license_text,
        )
        self.assertIn("THE SOFTWARE IS PROVIDED \"AS IS\"", self.license_text)
        self.assertIn("Copyright (c)", self.license_text)

    # -- 2: THIRD_PARTY_NOTICES.md exists and is substantive -----------------

    def test_02_third_party_notices_exists(self):
        self.assertTrue(NOTICES_PATH.is_file(), "THIRD_PARTY_NOTICES.md must exist")
        self.assertGreater(len(self.notices_text), 500)
        self.assertIn("licenses/", self.notices_text)

    # -- 3: licenses/ directory exists with the expected core files -----------

    def test_03_licenses_directory_has_required_files(self):
        self.assertTrue(LICENSES_DIR.is_dir(), "licenses/ directory must exist")
        for fname in REQUIRED_LICENSE_FILES:
            with self.subTest(fname=fname):
                self.assertTrue(
                    (LICENSES_DIR / fname).is_file(),
                    f"licenses/{fname} must exist",
                )

    # -- 4: README references MIT / links LICENSE -----------------------------

    def test_04_readme_references_mit_license(self):
        self.assertIn("MIT", self.readme_text)
        self.assertIn("(LICENSE)", self.readme_text)

    # -- 5: README links HOWTOUSE.md -------------------------------------------

    def test_05_readme_links_howtouse(self):
        self.assertIn("HOWTOUSE.md", self.readme_text)

    # -- 6: README links CHANGELOG.md ------------------------------------------

    def test_06_readme_links_changelog(self):
        self.assertIn("CHANGELOG.md", self.readme_text)

    # -- 7: README links THIRD_PARTY_NOTICES.md --------------------------------

    def test_07_readme_links_third_party_notices(self):
        self.assertIn("THIRD_PARTY_NOTICES.md", self.readme_text)

    # -- 8: HOWTOUSE contains a validation/self-test section -------------------

    def test_08_howtouse_contains_validation_section(self):
        self.assertTrue(HOWTOUSE_PATH.is_file(), "HOWTOUSE.md must exist")
        self.assertIn("Validation / Self-Test Checklist", self.howtouse_text)
        self.assertIn("Developer Validation", self.howtouse_text)

    # -- 9: CHANGELOG has an Unreleased pre-release structure -------------------

    def test_09_changelog_has_unreleased_structure(self):
        self.assertTrue(CHANGELOG_PATH.is_file(), "CHANGELOG.md must exist")
        self.assertIn("[Unreleased]", self.changelog_text)
        self.assertIn("not yet had a formal 0.69 release", self.changelog_text)

    # -- 10: packaging spec collects release docs -----------------------------

    def test_10_spec_collects_release_docs(self):
        self.assertTrue(SPEC_PATH.is_file(), "packaging/toroidamp.spec must exist")
        self.assertIn("_RELEASE_DOCS", self.spec_text)
        self.assertIn('"LICENSE"', self.spec_text)
        self.assertIn('"THIRD_PARTY_NOTICES.md"', self.spec_text)
        self.assertIn('"HOWTOUSE.md"', self.spec_text)
        self.assertIn('"licenses"', self.spec_text)

    # -- 11: pyproject.toml declares MIT expression cleanly ---------------------

    def test_11_pyproject_license_expression_clean(self):
        self.assertIn('license = "MIT"', self.pyproject_text)
        self.assertIn('license-files = ["LICENSE"]', self.pyproject_text)
        self.assertNotIn("License :: OSI Approved :: MIT License", self.pyproject_text)

    # -- 12: required license text files are present and non-empty -------------

    def test_12_required_license_files_non_empty(self):
        for fname in REQUIRED_LICENSE_FILES:
            path = LICENSES_DIR / fname
            with self.subTest(fname=fname):
                if path.is_file():
                    self.assertGreater(
                        len(path.read_text(encoding="utf-8", errors="replace")),
                        50,
                        f"licenses/{fname} should not be empty/near-empty",
                    )


if __name__ == "__main__":
    unittest.main()
