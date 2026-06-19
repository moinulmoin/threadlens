"""PyInstaller entry point for the threadlens CLI.

A non-relative import wrapper: ``threadlens/__main__.py`` uses ``from .cli import
main``, which only resolves when run via ``python -m threadlens``. PyInstaller
runs the entry script as top-level ``__main__``, so the frozen binary needs an
absolute import instead.
"""

from threadlens.cli import main

raise SystemExit(main())
