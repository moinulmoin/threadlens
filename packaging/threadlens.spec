# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller --onedir spec for the threadlens CLI (v1.1.0 native binaries).

onedir (COLLECT) is intentional, not onefile: onefile re-extracts ~10MB to a
temp dir on every run, which would dominate threadlens's sub-250ms search
latency (Raycast spawns a process per query) and break `threadlens skill`
(its _MEIPASS path vanishes on exit). onedir runs straight off disk.

Build:
    pyinstaller packaging/threadlens.spec --distpath dist/bin --workpath build/pyi --noconfirm
Output: dist/bin/threadlens/threadlens (executable) + dist/bin/threadlens/_internal/
"""

import os

from PyInstaller.utils.hooks import collect_data_files

# SPECPATH is injected by PyInstaller; the entry stub sits beside this spec and
# the repo root is its parent (so `import threadlens` resolves during analysis).
entry = os.path.join(SPECPATH, "threadlens_entry.py")
repo_root = os.path.dirname(SPECPATH)

# Bundle the package's non-Python data: skills/threadlens/SKILL.md and
# skills/threadlens/agents/*.yaml. cmd_skill reads these via importlib.resources.
datas = collect_data_files("threadlens")

a = Analysis(
    [entry],
    pathex=[repo_root],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir: binaries live in _internal/, not in the exe
    name="threadlens",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="threadlens",
)
