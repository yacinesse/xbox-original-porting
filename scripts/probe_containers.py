#!/usr/bin/env python3
"""Read-only Xbox game asset & proprietary container inspector.

Identifies known Xbox media signatures (XPR, XACT WBND/SDBK, Bink, XMV, DDS, WMA,
RenderWare, Unreal, zlib streams), probes common chunked/footer-table archive layouts,
computes Shannon entropy to distinguish raw vs compressed vs encrypted blocks, and
safely previews ASCII configuration/script text when present.

Usage:
    py -3 probe_containers.py path/to/assets_dir --recursive --json asset-probe.json
    py -3 probe_containers.py path/to/archive.dat --decompress-preview
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

KNOWN_MAGICS: Tuple[Tuple[int, bytes, str], ...] = (
    (0, b"XBEH", "Xbox Executable (XBE)"),
    (0, b"XPR0", "Xbox Packed Resource v0 (XPR0)"),
    (0, b"XPR1", "Xbox Packed Resource v1 (XPR1)"),
    (0, b"WBND", "XACT Wave Bank (.xwb)"),
    (0, b"SDBK", "XACT Sound Bank (.xsb)"),
    (0, b"BIKi", "RAD Bink Video (.bik)"),
    (0, b"KB2", "RAD Bink 2 Video (.bk2)"),
    (0, b"DDS ", "DirectDraw Surface (.dds)"),
    (0, b"RIFF", "RIFF / WAV / xWMA Container"),
    (0, b"\x89PNG\r\n\x1a\n", "PNG Image"),
    (0, b"OggS", "Ogg Container"),
    (0, b"\x30\x26\xb2\x75", "ASF / WMA Stream"),
    (0, b"\xc1\x83\x2a\x9e", "Unreal Engine Package (.utx/.ukx)"),
    (0, b"NetImmerse File Format", "NetImmerse / Gamebryo (.nif)"),
    (0, b"Gamebryo File Format", "Gamebryo (.nif)"),
    (0, b"\x10\x00\x00\x00", "Possible RenderWare Stream (RW Clump/TexDict)"),
    (16, b"xobX", "Xbox Media Video (.xmv)"),
)

ZLIB_HEADERS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")


def shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy in bits/byte over `data`."""
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def detect_magic(head: bytes) -> Optional[str]:
    """Identify known file magic signatures inside the first 64 bytes."""
    for offset, sig, label in KNOWN_MAGICS:
        if len(head) >= offset + len(sig) and head[offset : offset + len(sig)] == sig:
            return label
    return None


def find_zlib_offsets(buf: bytes, max_hits: int = 8) -> List[int]:
    """Scan `buf` for candidate zlib stream headers confirmed by partial decompression."""
    hits: List[int] = []
    for pos in range(0, max(0, len(buf) - 6)):
        if buf[pos : pos + 2] not in ZLIB_HEADERS:
            continue
        cmf, flg = buf[pos], buf[pos + 1]
        if ((cmf << 8) + flg) % 31 != 0:
            continue
        try:
            d = zlib.decompressobj()
            out = d.decompress(buf[pos : pos + 512], 256)
            if out:
                hits.append(pos)
                if len(hits) >= max_hits:
                    break
        except zlib.error:
            continue
    return hits


def check_prefixed_zlib(data: bytes) -> Optional[dict]:
    """Check for `[uint32_le uncomp_size][zlib_stream]` style compressed assets."""
    if len(data) < 10:
        return None
    for prefix_bytes in (4, 8):
        if len(data) < prefix_bytes + 6:
            continue
        uncomp_sz = struct.unpack_from("<I", data, 0)[0]
        if not (0 < uncomp_sz <= 64 * 1024 * 1024):
            continue
        if data[prefix_bytes : prefix_bytes + 2] not in ZLIB_HEADERS:
            continue
        try:
            dec = zlib.decompress(data[prefix_bytes:])
            if len(dec) == uncomp_sz:
                return {
                    "type": "length-prefixed-zlib",
                    "prefix_bytes": prefix_bytes,
                    "uncompressed_size": uncomp_sz,
                    "preview_ascii": safe_ascii_preview(dec[:256]),
                }
        except zlib.error:
            continue
    return None


def check_footer_table_archive(data: bytes) -> Optional[dict]:
    """Probe `(uint32 count, uint32 table_offset)` footer-table archives (e.g. chunked .dat)."""
    if len(data) < 24:
        return None
    count, table_off = struct.unpack_from("<II", data, 0)
    if not (1 <= count <= 200000 and 8 <= table_off < len(data)):
        return None
    rem = len(data) - table_off
    for stride in (16, 20, 24, 32):
        if count * stride == rem:
            return {
                "type": "footer-table-archive",
                "entry_count": count,
                "table_offset": f"0x{table_off:X}",
                "entry_stride": stride,
            }
    return None


def safe_ascii_preview(buf: bytes, limit: int = 160) -> Optional[str]:
    """Return a clean one-line ASCII preview if >=85% of bytes are printable/whitespace."""
    if not buf:
        return None
    printable = sum(1 for b in buf if (32 <= b <= 126) or b in (9, 10, 13))
    if printable / len(buf) < 0.85:
        return None
    text = buf[:limit].decode("latin-1", errors="replace")
    return " ".join(text.splitlines()).strip()


def probe_file(path: Path, max_read_bytes: int, preview_zlib: bool) -> dict:
    """Inspect a single file in read-only mode."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        sample = fh.read(min(size, max_read_bytes))

    head = sample[:64]
    magic = detect_magic(head)
    entropy_total = round(shannon_entropy(sample), 3)
    zlib_offs = find_zlib_offsets(sample[:65536])
    footer_info = check_footer_table_archive(sample) if size <= max_read_bytes else None
    prefixed_info = check_prefixed_zlib(sample) if size <= max_read_bytes else None

    if footer_info is None and size > max_read_bytes:
        # Still check the 8-byte header against the full file size cleanly
        if size >= 24:
            count, table_off = struct.unpack_from("<II", head, 0)
            rem = size - table_off
            for stride in (16, 20, 24, 32):
                if 1 <= count <= 200000 and 8 <= table_off < size and count * stride == rem:
                    footer_info = {
                        "type": "footer-table-archive",
                        "entry_count": count,
                        "table_offset": f"0x{table_off:X}",
                        "entry_stride": stride,
                    }
                    break

    zlib_preview = None
    if preview_zlib and zlib_offs:
        try:
            d = zlib.decompressobj()
            out = d.decompress(sample[zlib_offs[0] : zlib_offs[0] + 4096], 512)
            zlib_preview = safe_ascii_preview(out) or out[:32].hex(" ")
        except zlib.error:
            zlib_preview = None

    return {
        "path": str(path),
        "size": size,
        "entropy_bits": entropy_total,
        "magic": magic,
        "head_hex": sample[:16].hex(" "),
        "zlib_offsets": [f"0x{x:X}" for x in zlib_offs],
        "archive_pattern": footer_info or prefixed_info,
        "ascii_preview": safe_ascii_preview(sample[:512]),
        "zlib_preview": zlib_preview,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Read-only Xbox asset & unknown binary container analyzer."
    )
    parser.add_argument("target", type=Path, help="File or directory to inspect")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse subdirectories")
    parser.add_argument("--json", type=Path, help="Write JSON report to file")
    parser.add_argument(
        "--max-read-mb",
        type=int,
        default=32,
        help="Max MiB read per file for entropy/decompression checks (default: 32)",
    )
    parser.add_argument(
        "--decompress-preview",
        action="store_true",
        help="Attempt small safe preview decompression on first detected zlib stream",
    )
    parser.add_argument(
        "--extensions",
        default="",
        help="Optional comma-separated extensions filter (e.g. .dat,.bin,.zbg)",
    )
    return parser


def iter_targets(target: Path, recursive: bool, exts: set[str]) -> Iterable[Path]:
    """Yield files from a file or directory target."""
    if target.is_file():
        yield target
        return
    it = target.rglob("*") if recursive else target.glob("*")
    for p in sorted(it):
        if not p.is_file():
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        yield p


def main(argv: Optional[Iterable[str]] = None) -> int:
    """CLI entry point."""
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    if not args.target.exists():
        print(f"ERROR: Target not found: {args.target}", file=sys.stderr)
        return 1

    exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    max_bytes = max(1, args.max_read_mb) * 1024 * 1024
    results: List[dict] = []

    for path in iter_targets(args.target, args.recursive, exts):
        info = probe_file(path, max_bytes, args.decompress_preview)
        results.append(info)
        tag = info["magic"] or (
            info["archive_pattern"]["type"]
            if info["archive_pattern"]
            else (f"zlib@{info['zlib_offsets'][0]}" if info["zlib_offsets"] else "unknown")
        )
        print(f"{path.name:28s} | {info['size']:10d} B | H={info['entropy_bits']:5.2f} | {tag}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"Inspected {len(results)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
