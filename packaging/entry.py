"""PyInstaller entry point for the NCC desktop app.

Kept outside the ``ncc`` package so relative imports stay inside the package
when PyInstaller runs this file as ``__main__``.
"""

from ncc.main import main

raise SystemExit(main())
