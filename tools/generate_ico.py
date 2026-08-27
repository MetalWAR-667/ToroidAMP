"""
ToroidAMP - Windows ICO Generator

Generates a multi-resolution Windows .ico from the 512x512 branding master
(assets/branding/toroidamp_icon.png). Run manually whenever the master
branding PNG changes:

    python tools\\generate_ico.py

Requires Pillow — a dev-only tool dependency (`pip install .[dev]`), never
required to run ToroidAMP itself. Does not touch the creative source
artwork (assets/images/).
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required to run this tool: pip install .[dev]  (or: pip install Pillow)", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
MASTER_PNG = REPO_ROOT / "assets" / "branding" / "toroidamp_icon.png"
OUTPUT_ICO = REPO_ROOT / "assets" / "branding" / "toroidamp.ico"
PACKAGE_ICO = REPO_ROOT / "src" / "toroidamp" / "assets" / "branding" / "toroidamp.ico"

# Sensible Windows icon sizes — favicons/taskbar through large shell views.
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not MASTER_PNG.is_file():
        print(f"Branding master not found: {MASTER_PNG}", file=sys.stderr)
        return 1

    master = Image.open(MASTER_PNG).convert("RGBA")

    # Pillow's ICO writer resamples the *master* image independently for
    # each requested size — every entry in ICO_SIZES is generated directly
    # from the 512x512 source, never through repeated downsampling of an
    # already-shrunk intermediate. Alpha transparency is preserved.
    master.save(OUTPUT_ICO, format="ICO", sizes=ICO_SIZES)
    print(f"Generated {OUTPUT_ICO}")
    print(f"  sizes: {ICO_SIZES}")

    PACKAGE_ICO.parent.mkdir(parents=True, exist_ok=True)
    master.save(PACKAGE_ICO, format="ICO", sizes=ICO_SIZES)
    print(f"Generated {PACKAGE_ICO} (packaged copy, for future executable/installer packaging)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
