#!/usr/bin/env python3
"""Scan Original Xbox XBE read-only/data sections for C++ vtables and function pointers.

Outputs candidate function entry points in xboxrecomp's `--seed-functions` JSON format
(`[{"start": "0x00136F40"}, ...]`), while guarding against mid-function split hazards when
an existing `functions.json` from `tools.disasm` is provided.

Usage:
    py -3 scan_vtables.py path/to/default.xbe -o seed_functions.json
    py -3 scan_vtables.py path/to/default.xbe --functions disasm/functions.json -o missing_seeds.json
"""

from __future__ import annotations

import argparse
import bisect
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import xbe_inspect  # noqa: E402

SECTION_FLAG_EXECUTABLE = 0x04

# Common x86-32 MSVC/XDK function prologue prefixes (used for scoring/filtering).
PROLOGUE_PREFIXES: Tuple[bytes, ...] = (
    b"\x55\x8b\xec",         # push ebp; mov ebp, esp
    b"\x55\x89\xe5",         # push ebp; mov ebp, esp (alt encoding)
    b"\x83\xec",             # sub esp, imm8
    b"\x81\xec",             # sub esp, imm32
    b"\x6a\xff\x68",         # push -1; push SEH_handler (__SEH_prolog)
    b"\xb8",                 # mov eax, imm32 (often SEH helper / switch)
    b"\x53\x56",             # push ebx; push esi
    b"\x53\x57",             # push ebx; push edi
    b"\x56\x57",             # push esi; push edi
    b"\x51",                 # push ecx
    b"\x53",                 # push ebx
    b"\x56",                 # push esi
    b"\x57",                 # push edi
    b"\x8b\x44\x24",         # mov eax, [esp+...]
    b"\x8b\x4c\x24",         # mov ecx, [esp+...]
    b"\x8b\x54\x24",         # mov edx, [esp+...]
    b"\xa1",                 # mov eax, [mem]
    b"\x33\xc0\xc3",         # xor eax, eax; ret
    b"\xb0\x01\xc3",         # mov al, 1; ret
    b"\xc2",                 # ret imm16
    b"\xc3",                 # ret
)


@dataclass(frozen=True)
class MappedSection:
    """In-memory view of an XBE section backed by raw file bytes."""

    name: str
    va_start: int
    va_size: int
    raw_addr: int
    raw_size: int
    is_code: bool


def build_sections(xbe_info: dict, extra_code: set[str]) -> List[MappedSection]:
    """Build sorted section descriptors from `xbe_inspect.parse_xbe` output."""
    out: List[MappedSection] = []
    for sec in xbe_info.get("sections", []):
        flags = int(sec["flags"])
        name = str(sec["name"])
        is_code = bool(flags & SECTION_FLAG_EXECUTABLE) or (name in extra_code)
        out.append(
            MappedSection(
                name=name,
                va_start=int(sec["virtual_addr"]),
                va_size=int(sec["virtual_size"]),
                raw_addr=int(sec["raw_addr"]),
                raw_size=int(sec["raw_size"]),
                is_code=is_code,
            )
        )
    return out


def va_to_offset(sections: Sequence[MappedSection], va: int) -> Optional[Tuple[MappedSection, int]]:
    """Translate a guest virtual address to a file byte offset within its section."""
    for sec in sections:
        if sec.va_start <= va < sec.va_start + sec.raw_size:
            return sec, sec.raw_addr + (va - sec.va_start)
    return None


def looks_like_code_entry(data: bytes, file_off: int) -> bool:
    """Check that target bytes are valid instructions rather than padding (`00`/`CC`)."""
    if file_off < 0 or file_off >= len(data):
        return False
    head = data[file_off : file_off + 16]
    if not head:
        return False
    if head[0] in (0x00, 0xCC, 0x90):
        return False
    if len(head) >= 4 and head[:4] == b"\x00\x00\x00\x00":
        return False
    return True


def matches_prologue(data: bytes, file_off: int) -> bool:
    """Return True if bytes at `file_off` match a known x86-32 function prologue."""
    head = data[file_off : file_off + 12]
    return any(head.startswith(p) for p in PROLOGUE_PREFIXES)


def load_known_functions(path: Optional[Path]) -> Tuple[set[int], List[Tuple[int, int]]]:
    """Load `xboxrecomp` `functions.json` (starts + [start, end) ranges)."""
    starts: set[int] = set()
    ranges: List[Tuple[int, int]] = []
    if not path:
        return starts, ranges
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.values() if isinstance(raw, dict) else raw
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        s = entry.get("start")
        e = entry.get("end")
        if s is None:
            continue
        sa = int(s, 16) if isinstance(s, str) else int(s)
        starts.add(sa)
        if e is not None:
            ea = int(e, 16) if isinstance(e, str) else int(e)
            if ea > sa:
                ranges.append((sa, ea))
    ranges.sort()
    return starts, ranges


def is_interior_address(ranges: Sequence[Tuple[int, int]], range_starts: Sequence[int], addr: int) -> bool:
    """Return True if `addr` lies strictly inside an already detected function body."""
    idx = bisect.bisect_left(range_starts, addr)
    if idx == 0:
        return False
    sa, ea = ranges[idx - 1]
    return sa < addr < ea


def scan_pointer_runs(
    data: bytes,
    sections: Sequence[MappedSection],
    scan_names: set[str],
    min_run: int,
    strict_prologue: bool,
) -> List[dict]:
    """Scan selected sections for aligned `uint32_le` runs targeting executable sections."""
    code_secs = [s for s in sections if s.is_code and s.raw_size > 0]
    code_ranges = [(s.va_start, s.va_start + s.raw_size) for s in code_secs]

    def in_code(va: int) -> bool:
        for lo, hi in code_ranges:
            if lo <= va < hi:
                return True
        return False

    vtables: List[dict] = []
    for sec in sections:
        if sec.name not in scan_names or sec.raw_size < 4:
            continue
        raw_end = min(len(data), sec.raw_addr + sec.raw_size)
        cur_start_va = 0
        cur_targets: List[int] = []

        def flush_run() -> None:
            if len(cur_targets) >= min_run:
                vtables.append(
                    {
                        "section": sec.name,
                        "table_va": f"0x{cur_start_va:08X}",
                        "slot_count": len(cur_targets),
                        "targets": cur_targets.copy(),
                    }
                )

        pos = sec.raw_addr
        while pos + 4 <= raw_end:
            va = struct.unpack_from("<I", data, pos)[0]
            valid = False
            if in_code(va):
                mapped = va_to_offset(code_secs, va)
                if mapped is not None:
                    _, off = mapped
                    if looks_like_code_entry(data, off):
                        valid = (not strict_prologue) or matches_prologue(data, off)
            if valid:
                if not cur_targets:
                    cur_start_va = sec.va_start + (pos - sec.raw_addr)
                cur_targets.append(va)
            else:
                flush_run()
                cur_targets.clear()
            pos += 4
        flush_run()
    return vtables


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Scan an Original Xbox XBE (.rdata/.data) for C++ vtable function pointers."
    )
    parser.add_argument("xbe", type=Path, help="Path to default.xbe")
    parser.add_argument("-o", "--output", type=Path, help="Write JSON output file")
    parser.add_argument(
        "--format",
        choices=("seeds", "detailed"),
        default="seeds",
        help="Output format: xboxrecomp `seeds` list (default) or `detailed` report",
    )
    parser.add_argument(
        "--scan-sections",
        default=".rdata,.data",
        help="Comma-separated sections to scan for pointer tables (default: .rdata,.data)",
    )
    parser.add_argument(
        "--extra-code-sections",
        default="",
        help="Comma-separated extra non-executable section names that also hold code",
    )
    parser.add_argument(
        "--min-run",
        type=int,
        default=3,
        help="Minimum contiguous code pointers to qualify as a vtable (default: 3)",
    )
    parser.add_argument(
        "--strict-prologue",
        action="store_true",
        help="Require each pointer target to match common x86-32 prologue opcodes",
    )
    parser.add_argument(
        "--functions",
        type=Path,
        help="Optional xboxrecomp functions.json to filter known starts & flag interior hazards",
    )
    parser.add_argument(
        "--include-known",
        action="store_true",
        help="Include targets already present in --functions (interior hazards remain excluded)",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    """CLI entry point."""
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    if not args.xbe.is_file():
        print(f"ERROR: XBE not found: {args.xbe}", file=sys.stderr)
        return 1

    data = args.xbe.read_bytes()
    xbe_info = xbe_inspect.parse_xbe(data, verify_sha1=False)
    extra_code = {s.strip() for s in args.extra_code_sections.split(",") if s.strip()}
    scan_secs = {s.strip() for s in args.scan_sections.split(",") if s.strip()}
    sections = build_sections(xbe_info, extra_code)

    vtables = scan_pointer_runs(
        data=data,
        sections=sections,
        scan_names=scan_secs,
        min_run=max(1, args.min_run),
        strict_prologue=args.strict_prologue,
    )

    known_starts, known_ranges = load_known_functions(args.functions)
    range_starts = [r[0] for r in known_ranges]

    all_targets = sorted({t for vt in vtables for t in vt["targets"]})
    skipped_interior: List[int] = []
    skipped_known: List[int] = []
    seeds: List[int] = []

    for addr in all_targets:
        if known_ranges and is_interior_address(known_ranges, range_starts, addr):
            skipped_interior.append(addr)
            continue
        if (not args.include_known) and (addr in known_starts):
            skipped_known.append(addr)
            continue
        seeds.append(addr)

    if args.format == "seeds":
        payload: object = [{"start": f"0x{addr:08X}"} for addr in seeds]
    else:
        payload = {
            "xbe": str(args.xbe),
            "title_id": xbe_info["certificate"]["title_id"],
            "title_name": xbe_info["certificate"]["title_name"],
            "vtable_runs": len(vtables),
            "unique_targets": len(all_targets),
            "skipped_known_count": len(skipped_known),
            "skipped_interior_count": len(skipped_interior),
            "skipped_interior_sample": [f"0x{a:08X}" for a in skipped_interior[:25]],
            "seed_count": len(seeds),
            "seeds": [f"0x{a:08X}" for a in seeds],
            "vtables": [
                {
                    "section": vt["section"],
                    "table_va": vt["table_va"],
                    "slot_count": vt["slot_count"],
                    "targets": [f"0x{a:08X}" for a in vt["targets"]],
                }
                for vt in vtables
            ],
        }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        f"TitleID={xbe_info['certificate']['title_id']} | vtables={len(vtables)} | "
        f"unique_targets={len(all_targets)} | known_skipped={len(skipped_known)} | "
        f"interior_blocked={len(skipped_interior)} | output_seeds={len(seeds)}"
    )
    if skipped_interior:
        print(
            f"NOTE: Blocked {len(skipped_interior)} pointer(s) sitting strictly inside "
            f"known functions to prevent mid-instruction splits.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
