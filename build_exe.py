"""
Build script — creates a standalone HebrewKeyboardFixer.exe
Run once on a machine with Python; distribute the resulting exe anywhere.
"""

import subprocess
import sys
import os
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).parent.resolve()
DIST_DIR   = SCRIPT_DIR / 'dist'
EXE_NAME   = 'HebrewKeyboardFixer'

REQUIRED_PACKAGES = ['pynput', 'pystray', 'pillow', 'pyinstaller', 'pyspellchecker']

HIDDEN_IMPORTS = [
    'pystray._win32',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'PIL._tkinter_finder',
]


def pip_install(packages):
    print(f"  Installing: {', '.join(packages)} ...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', *packages, '--quiet'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Error: {result.stderr.strip()}")
        return False
    return True


def build():
    print("=" * 55)
    print("  Hebrew Keyboard Fixer — Production EXE Build")
    print("=" * 55)

    if sys.platform != 'win32':
        print("ERROR: Can only build on Windows.")
        sys.exit(1)

    print("\n[1/3] Installing dependencies...")
    if not pip_install(REQUIRED_PACKAGES):
        print("ERROR: Installation failed.")
        sys.exit(1)
    print("  OK")

    add_data_args = []
    data_dir = SCRIPT_DIR / 'data'
    if data_dir.exists():
        add_data_args += ['--add-data', f'{data_dir};data']
        print(f"  Bundling word lists from: {data_dir}")

    hebrew_wordlist = SCRIPT_DIR / 'hebrew_words.txt'
    if hebrew_wordlist.exists():
        add_data_args += ['--add-data', f'{hebrew_wordlist};.']
        print(f"  Bundling Hebrew dictionary: {hebrew_wordlist} ({hebrew_wordlist.stat().st_size // 1024} KB)")
    else:
        print("  WARNING: hebrew_words.txt not found — run download_hebrew_dict.py first")

    version_file = SCRIPT_DIR / 'version_info.txt'

    print("\n[2/3] Building EXE (this takes about a minute)...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',           # no console window
        '--name', EXE_NAME,
        '--distpath', str(DIST_DIR),
        '--workpath', str(SCRIPT_DIR / 'build'),
        '--specpath', str(SCRIPT_DIR),
        '--upx-dir', '',        # effectively disables UPX even if installed
        '--noupx',              # explicit: do not compress with UPX
        '--collect-data', 'spellchecker',     # bundle pyspellchecker dictionary data files
        *[f'--hidden-import={h}' for h in HIDDEN_IMPORTS],
        *(['--version-file', str(version_file)] if version_file.exists() else []),
        *add_data_args,
        str(SCRIPT_DIR / 'tray_app.py'),
    ]

    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))

    exe_path = DIST_DIR / f'{EXE_NAME}.exe'
    print("\n[3/3] Verifying output...")

    if result.returncode == 0 and exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 55}")
        print(f"SUCCESS — ready to distribute:")
        print(f"   {exe_path}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"\nNo Python required on the target machine.")
        print('=' * 55)
    else:
        print("ERROR: Build failed. See output above for details.")
        sys.exit(1)


if __name__ == '__main__':
    build()
