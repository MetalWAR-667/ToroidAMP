"""
tests/test_rc_069_003.py — RC-069-003: PyInstaller ONEDIR Packaging Contracts

These validate the packaging CONTRACT (spec file content, config wiring,
path independence) — not a substitute for actually running the frozen
ToroidAMP.exe, which remains mandatory human validation (see
docs/release/RC_069_003_pyinstaller_onedir.md §"Human Validation Protocol").

Covers:
1.  Spec/build config exists.
2.  Package metadata collection configured (--copy-metadata equivalent).
3.  Product asset collection configured.
4.  libxmp/pygame binary collection strategy configured.
5.  Writable paths remain outside any package/dist resource tree.
6.  Generated build/dist dirs are git-ignored.
7.  Canonical entry point unchanged (packaging/run_toroidamp.py calls the
    exact same toroidamp.__main__.main as `python -m toroidamp`).
8.  Version source remains valid (unchanged from RC-069-002's contract).
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "packaging" / "toroidamp.spec"
ENTRY_SCRIPT_PATH = REPO_ROOT / "packaging" / "run_toroidamp.py"


class TestRC069003PackagingContracts(unittest.TestCase):

    def setUp(self):
        if SPEC_PATH.is_file():
            self.spec_text = SPEC_PATH.read_text(encoding="utf-8")
        else:
            self.spec_text = ""

    # -- 1: spec/build config exists ------------------------------------------

    def test_01_spec_and_entry_script_exist(self):
        self.assertTrue(SPEC_PATH.is_file(), "packaging/toroidamp.spec must exist")
        self.assertTrue(ENTRY_SCRIPT_PATH.is_file(), "packaging/run_toroidamp.py must exist")

    # -- 2: package metadata collection -----------------------------------------

    def test_02_metadata_collection_configured(self):
        self.assertIn("copy_metadata", self.spec_text)
        self.assertIn('copy_metadata("toroidamp")', self.spec_text)

    # -- 3: product asset collection --------------------------------------------

    def test_03_asset_collection_configured(self):
        self.assertIn("collect_data_files", self.spec_text)
        self.assertIn('collect_data_files("toroidamp")', self.spec_text)

    # -- 4: libxmp/pygame binary collection ---------------------------------------

    def test_04_pygame_binary_collection_configured(self):
        self.assertIn("collect_dynamic_libs", self.spec_text)
        self.assertIn('collect_dynamic_libs("pygame")', self.spec_text)

    def test_04b_pyttsx3_hidden_import_configured(self):
        self.assertIn("pyttsx3.drivers.sapi5", self.spec_text)

    # -- 5: writable paths outside any resource tree ------------------------------

    def test_05_writable_paths_outside_repo_and_package(self):
        from toroidamp.paths import get_app_data_dir
        app_data = get_app_data_dir()
        # Never inside the repo checkout (which is what a naive dist/-relative
        # or CWD-relative writable path would risk).
        self.assertFalse(str(app_data).lower().startswith(str(REPO_ROOT).lower()))
        # Never inside the package's own installed/frozen resource directory.
        import toroidamp
        pkg_dir = Path(toroidamp.__file__).resolve().parent
        self.assertFalse(str(app_data).lower().startswith(str(pkg_dir).lower()))

    # -- 6: generated dirs git-ignored --------------------------------------------

    def test_06_build_and_dist_are_gitignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("build/", gitignore)
        self.assertIn("dist/", gitignore)

    # -- 7: canonical entry point unchanged ---------------------------------------

    def test_07_entry_script_calls_canonical_main(self):
        import ast
        entry_src = ENTRY_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("from toroidamp.__main__ import main", entry_src)
        self.assertIn("main()", entry_src)
        # No alternative startup wiring — parse the AST and confirm the only
        # top-level statements are the import and an `if __name__ ==
        # "__main__": main()` guard (or an equivalent bare call).
        tree = ast.parse(entry_src)
        top_level_kinds = [type(node).__name__ for node in tree.body]
        self.assertLessEqual(len(top_level_kinds), 3)  # docstring + import + if-guard
        self.assertIn("ImportFrom", top_level_kinds)

    def test_07b_console_script_and_module_invocation_agree(self):
        import tomllib
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["project"]["scripts"]["toroidamp"], "toroidamp.__main__:main")

    # -- 8: version source remains valid ------------------------------------------

    def test_08_version_source_valid(self):
        from toroidamp._version import resolve_version, _from_pyproject
        self.assertIsNotNone(_from_pyproject())
        version = resolve_version()
        self.assertRegex(version, r"^\d+\.\d+")

    def test_08b_editable_install_metadata_matches_pyproject(self):
        """
        Regression for the RC-069-003 frozen-only defect: a stale editable-
        install dist-info version silently bakes into copy_metadata()'s
        output. This is the dev-environment-hygiene check that would have
        caught it before a build, not just after inspecting dist/.
        """
        import importlib.metadata as m
        import tomllib
        pyproject_version = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        installed_version = m.version("toroidamp")
        self.assertEqual(
            installed_version, pyproject_version,
            f"editable-install metadata ({installed_version}) is stale vs. pyproject.toml "
            f"({pyproject_version}) — run `pip install -e . --no-deps` before building"
        )


if __name__ == "__main__":
    unittest.main()
