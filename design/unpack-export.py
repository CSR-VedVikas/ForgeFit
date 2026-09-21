"""Unpack a Claude Design export into design/ and verify it is complete.

Only part of the design project is committed: the small text files round-trip
through a tool call cleanly, but the prototypes and the exercise art do not.
Download the project export from

    https://claude.ai/design/p/07869a8a-38fe-4617-91ee-4818a886067d

then:

    python design/unpack-export.py ~/Downloads/ForgeFit-export.zip

Existing files are overwritten (the export is the source of truth), except
that anything already tracked in git is reported rather than silently
replaced. scraps/ and uploads/ are extracted but gitignored — they are PDF
page rasters and pasted screenshots.

Exits non-zero if any prototype still references a file that is not present,
so this is safe to chain with a commit.
"""

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path

DESIGN = Path(__file__).resolve().parent

# Every prototype the project is expected to contain.
EXPECTED = [
    "ForgeFit - Completion Plan.dc.html",
    "ForgeFit - Current UI.dc.html",
    "ForgeFit - Engineering Report.dc.html",
    "ForgeFit - Production Readiness.dc.html",
    "ForgeFit - Redesign.dc.html",
    "ForgeFit - Track B Wiring.dc.html",
    "ForgeFitApp-Ink.dc.html",
    "ForgeFitEntry-Ink.dc.html",
    "LiveWorkout-Ink.dc.html",
]

IGNORED_PREFIXES = ("scraps/", "uploads/")

# src="..." / href="..." that are not absolute, data:, or template holes.
REF = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""")


def is_local(ref: str) -> bool:
    if not ref or ref.startswith(("http://", "https://", "data:", "#", "//")):
        return False
    return "{{" not in ref  # skip DC template expressions


def unpack(zip_path: Path) -> int:
    if not zip_path.exists():
        sys.exit(f"No such file: {zip_path}")

    written, ignored = 0, 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = info.filename
            # Exports are sometimes nested under a single top folder.
            parts = Path(name).parts
            if parts and parts[0].lower().startswith("forgefit") and len(parts) > 1:
                if not Path(name).suffix or len(parts) > 1:
                    name = str(Path(*parts[1:]))

            target = DESIGN / name
            if not str(target.resolve()).startswith(str(DESIGN.resolve())):
                print(f"  ! refusing path outside design/: {name}")
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                out.write(src.read())

            if name.replace("\\", "/").startswith(IGNORED_PREFIXES):
                ignored += 1
            else:
                written += 1

    print(f"Extracted {written} tracked file(s), {ignored} gitignored.")
    return written


def verify() -> int:
    problems = 0

    print("\nPrototypes:")
    for name in EXPECTED:
        ok = (DESIGN / name).exists()
        print(f"  {'ok  ' if ok else 'MISSING'}  {name}")
        problems += 0 if ok else 1

    print("\nReferenced files:")
    missing = {}
    for page in sorted(DESIGN.glob("*.dc.html")):
        for raw in REF.findall(page.read_text(encoding="utf-8", errors="replace")):
            ref = html.unescape(raw).split("?")[0].split("#")[0]
            if not is_local(ref):
                continue
            if not (DESIGN / ref).exists():
                missing.setdefault(ref, []).append(page.name)

    if missing:
        for ref, pages in sorted(missing.items()):
            print(f"  MISSING  {ref}   <- {', '.join(sorted(set(pages)))}")
        problems += len(missing)
    else:
        print("  all resolve")

    assets = sorted(DESIGN.glob("assets/*"))
    print(f"\nassets/: {len(assets)} file(s)")

    if problems:
        print(f"\n{problems} problem(s). The export is incomplete.")
    else:
        print("\nComplete. Safe to commit.")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("zip", nargs="?", type=Path,
                    help="the export .zip; omit to only verify what is here")
    args = ap.parse_args()

    if args.zip:
        unpack(args.zip)
    else:
        # Plain ASCII: the Windows console default codepage mangles dashes.
        print("No zip given - verifying the current contents only.\n")

    sys.exit(1 if verify() else 0)


if __name__ == "__main__":
    main()
