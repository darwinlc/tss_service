"""Build the distribution zips (code only: no .venv, weights, repo or outputs).

Usage:  .venv\\Scripts\\python.exe package.py

Writes two files next to the portal folder:
  ming-tts-portal-package.zip  the normal package
  ming-tts-portal-email.zip    same, but .bat/.ps1 are stored as .txt so mail
                               filters (Gmail blocks .bat, even inside a zip) let it through
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ["app.py", "cues.py", "engine.py", "check.py", "package.py", "requirements.txt",
         "requirements-optional.txt", "setup.bat", "run.bat", "run.ps1", "SETUP.md"]
FOLDERS = ["static", "samples"]
SCRIPT_SUFFIXES = {".bat", ".ps1"}

RENAME_NOTE = """This package was made email-safe: Gmail and some other filters block .bat files.
Before following SETUP.md, rename these three files (remove the trailing .txt):

    setup.bat.txt  ->  setup.bat
    run.bat.txt    ->  run.bat
    run.ps1.txt    ->  run.ps1

In PowerShell, from this folder, in one go:

    Get-ChildItem *.bat.txt, *.ps1.txt | Rename-Item -NewName { $_.Name -replace '\\.txt$', '' }

Then continue with SETUP.md.
"""


def build(out, email_safe):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            stored = name + ".txt" if email_safe and Path(name).suffix in SCRIPT_SUFFIXES else name
            bundle.write(ROOT / name, f"ming-tts-portal/{stored}")
        for folder in FOLDERS:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    bundle.write(path, f"ming-tts-portal/{path.relative_to(ROOT).as_posix()}")
        # Empty folders the guide tells you to fill.
        for folder in ("models", "vendor"):
            bundle.writestr(f"ming-tts-portal/{folder}/README.txt",
                            f"Put the {folder} content here; see SETUP.md.\n")
        if email_safe:
            bundle.writestr("ming-tts-portal/READ-ME-FIRST.txt", RENAME_NOTE)
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


build(ROOT.parent / "ming-tts-portal-package.zip", email_safe=False)
build(ROOT.parent / "ming-tts-portal-email.zip", email_safe=True)
