"""
ToroidAMP - PyInstaller Entry Script (RC-069-003)

PyInstaller's Analysis() needs a real .py script as its entry point (not a
bare `python -m toroidamp` module invocation) — this is a thin, 2-line
launcher that calls the exact same canonical entry point the `toroidamp`
console script and `python -m toroidamp` both already use. No alternative
startup architecture: this is the same `main()`, nothing more.
"""

from toroidamp.__main__ import main

if __name__ == "__main__":
    main()
