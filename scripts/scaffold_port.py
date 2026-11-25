#!/usr/bin/env python3
"""
scaffold_port.py - Create a clean, game-data-free Xbox-to-Windows porting workspace.

Generates the recommended directory layout (`docs/`, `reports/`, `runtime/`, `tools/`,
`games/<title-id>-<slug>/`, and gitignored `private/`), plus a strict `.gitignore` that
keeps copyrighted game dumps, extracted assets, and generated C out of version control.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GITIGNORE_CONTENT = """# Original Xbox Porting - Keep game data and generated artifacts out of Git
Game/
private/
assets/
extracted/
build/
out/
saves/
tools/external/
*.iso
*.xiso
*.xbe
*.xpr
*.xwb
*.xsb
*.xmv
*.bik
*.wma
*.pdb
*.dmp
*.exe
*.bmp
*.png
*.log
"""

DIRS = [
    "docs/adr",
    "reports",
    "tools/extraction",
    "tools/analysis",
    "tools/testing",
    "runtime/kernel",
    "runtime/graphics",
    "runtime/audio",
    "runtime/input",
    "runtime/filesystem",
    "runtime/common",
    "third_party",
    "data/xdk-signatures",
    "private/dumps",
    "private/extracted",
    "private/generated",
    "private/logs",
]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "xbox-title"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a clean Xbox Original PC porting project workspace."
    )
    parser.add_argument("target", type=Path, help="Destination project root directory")
    parser.add_argument("--title-id", required=True, help="8-hex-digit Xbox Title ID (e.g., 4D530004)")
    parser.add_argument("--name", required=True, help="Game title or project slug")
    args = parser.parse_args()

    if not re.fullmatch(r"[0-9A-Fa-f]{8}", args.title_id):
        print(f"Error: --title-id must be 8 hex characters (got '{args.title_id}')", file=sys.stderr)
        return 1

    root = args.target.resolve()
    root.mkdir(parents=True, exist_ok=True)

    for rel in DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    game_dir = root / "games" / f"{args.title_id.upper()}-{slugify(args.name)}"
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "overrides").mkdir(exist_ok=True)

    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE_CONTENT, encoding="utf-8")

    notes = game_dir / "notes.md"
    if not notes.exists():
        notes.write_text(
            f"# {args.name} ({args.title_id.upper()}) — Porting Notes\n\n"
            "- **Status:** Assessment\n"
            "- **Target Tier:** Tier 0 (Boot to title screen)\n"
            "- **Source Dump:** Stored locally in `private/dumps/` (never committed)\n",
            encoding="utf-8",
        )

    gate_log = root / "reports" / "gate-log.md"
    if not gate_log.exists():
        gate_log.write_text(
            "# Gate Verification Log\n\n"
            "| Gate | Date | Commit / Tool Versions | Evidence / Command Output | Status |\n"
            "|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    print(f"Scaffolded porting workspace at: {root}")
    print(f"Game metadata directory:         {game_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
