#!/usr/bin/env python3
"""
xiso_inspect.py - Read-only Original Xbox XDVDFS (XISO / XGD) inspector & extractor.

Supports standard XISO (offset 0), XGD1 (405798912), XGD2 (265879552), and XGD3 (34078720).
Reads volume metadata, lists directory trees, verifies file hashes, and extracts files
without modifying the source image. Uses Python 3.10+ standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

SECTOR_SIZE = 2048
VOLUME_SECTOR = 32
VOLUME_MAGIC = b"MICROSOFT*XBOX*MEDIA"

# Partition offsets (bytes) verified against antangelo/xdvdfs
XDVDFS_OFFSETS: dict[str, int] = {
    "XISO": 0,
    "XGD1": 405798912,
    "XGD2": 265879552,
    "XGD3": 34078720,
}

ATTR_READ_ONLY = 0x01
ATTR_HIDDEN = 0x02
ATTR_SYSTEM = 0x04
ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE = 0x20
ATTR_NORMAL = 0x80


@dataclass
class VolumeInfo:
    format_type: str
    partition_offset: int
    root_sector: int
    root_size: int
    filetime: int


@dataclass
class FileEntry:
    path: str
    is_dir: bool
    sector: int
    size: int
    attributes: int
    sha256: str | None = None


def detect_volume(fp: BinaryIO, file_size: int) -> VolumeInfo:
    """Detect XDVDFS magic at known XISO/XGD offsets."""
    for fmt, base_offset in XDVDFS_OFFSETS.items():
        vol_offset = base_offset + VOLUME_SECTOR * SECTOR_SIZE
        if vol_offset + SECTOR_SIZE > file_size:
            continue
        fp.seek(vol_offset)
        sector_data = fp.read(SECTOR_SIZE)
        if len(sector_data) < SECTOR_SIZE:
            continue
        if sector_data[0:20] == VOLUME_MAGIC and sector_data[0x7EC:0x800] == VOLUME_MAGIC:
            root_sector, root_size, filetime = struct.unpack_from("<IIQ", sector_data, 20)
            return VolumeInfo(
                format_type=fmt,
                partition_offset=base_offset,
                root_sector=root_sector,
                root_size=root_size,
                filetime=filetime,
            )
    raise ValueError("Valid XDVDFS volume header ('MICROSOFT*XBOX*MEDIA') not found at known offsets.")


def _read_dirent_tree(
    fp: BinaryIO,
    base_offset: int,
    table_sector: int,
    table_size: int,
    parent_path: str,
    compute_hash: bool,
) -> list[FileEntry]:
    """Traverse an XDVDFS binary search tree directory table in preorder."""
    if table_sector == 0 or table_size == 0:
        return []

    table_start = base_offset + table_sector * SECTOR_SIZE
    fp.seek(table_start)
    table_bytes = fp.read(table_size)
    if len(table_bytes) < table_size:
        raise ValueError(f"Truncated directory table at sector {table_sector}")

    entries: list[FileEntry] = []
    stack: list[int] = [0]
    visited: set[int] = set()

    while stack:
        rel_off = stack.pop()
        if rel_off in visited or rel_off + 14 > len(table_bytes):
            continue
        visited.add(rel_off)

        raw_hdr = table_bytes[rel_off : rel_off + 14]
        if raw_hdr == b"\xff" * 14 or raw_hdr == b"\x00" * 14:
            continue

        left_off, right_off, data_sector, data_size, attrs, name_len = struct.unpack(
            "<HHIIBB", raw_hdr
        )
        name_start = rel_off + 14
        name_end = name_start + name_len
        if name_end > len(table_bytes):
            raise ValueError(f"Directory entry filename exceeds table bounds at offset {rel_off}")

        name = table_bytes[name_start:name_end].decode("utf-8", errors="replace")
        full_path = f"{parent_path}/{name}" if parent_path else name
        is_dir = bool(attrs & ATTR_DIRECTORY)

        if right_off not in (0, 0xFFFF):
            stack.append(right_off * 4)
        if left_off not in (0, 0xFFFF):
            stack.append(left_off * 4)

        file_hash: str | None = None
        if not is_dir and compute_hash and data_size > 0:
            file_hash = _hash_region(fp, base_offset + data_sector * SECTOR_SIZE, data_size)
        elif not is_dir and compute_hash and data_size == 0:
            file_hash = hashlib.sha256(b"").hexdigest()

        entries.append(
            FileEntry(
                path=full_path,
                is_dir=is_dir,
                sector=data_sector,
                size=data_size,
                attributes=attrs,
                sha256=file_hash,
            )
        )

        if is_dir and data_sector != 0 and data_size != 0:
            entries.extend(
                _read_dirent_tree(
                    fp, base_offset, data_sector, data_size, full_path, compute_hash
                )
            )

    return entries


def _hash_region(fp: BinaryIO, offset: int, size: int) -> str:
    h = hashlib.sha256()
    fp.seek(offset)
    remaining = size
    while remaining > 0:
        chunk = fp.read(min(65536, remaining))
        if not chunk:
            raise ValueError(f"Unexpected EOF while reading {size} bytes at {offset:#x}")
        h.update(chunk)
        remaining -= len(chunk)
    return h.hexdigest()


def extract_entries(
    fp: BinaryIO,
    vol: VolumeInfo,
    entries: list[FileEntry],
    out_dir: Path,
    read_only: bool = True,
) -> dict[str, int]:
    """Extract all entries safely into out_dir, preventing path traversal."""
    out_dir_resolved = out_dir.resolve()
    out_dir_resolved.mkdir(parents=True, exist_ok=True)

    counts = {"dirs": 0, "files": 0, "bytes": 0}
    for entry in entries:
        # Sanitize relative path components
        parts = [p for p in entry.path.split("/") if p not in ("", ".", "..")]
        if not parts:
            continue
        target = (out_dir_resolved / Path(*parts)).resolve()
        if out_dir_resolved not in target.parents and target != out_dir_resolved:
            raise ValueError(f"Refusing path traversal target: {entry.path}")

        if entry.is_dir:
            target.mkdir(parents=True, exist_ok=True)
            counts["dirs"] += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                os.chmod(target, 0o644)
            fp.seek(vol.partition_offset + entry.sector * SECTOR_SIZE)
            remaining = entry.size
            with open(target, "wb") as out_f:
                while remaining > 0:
                    chunk = fp.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError(f"Unexpected EOF extracting {entry.path}")
                    out_f.write(chunk)
                    remaining -= len(chunk)
            if read_only:
                os.chmod(target, 0o444)
            counts["files"] += 1
            counts["bytes"] += entry.size

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or extract an Original Xbox XDVDFS (XISO/XGD) disc image."
    )
    parser.add_argument("image", type=Path, help="Path to the .iso/.xiso image (read-only)")
    parser.add_argument(
        "--extract",
        type=Path,
        default=None,
        help="Optional destination directory to extract contents into",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional path to write JSON manifest (with SHA-256 hashes)",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip per-file SHA-256 computation for faster listing",
    )
    parser.add_argument(
        "--writable",
        action="store_true",
        help="Do not mark extracted files read-only (default marks extracted files 0444)",
    )
    args = parser.parse_args()

    if not args.image.is_file():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        return 1

    file_size = args.image.stat().st_size
    with open(args.image, "rb") as fp:
        vol = detect_volume(fp, file_size)
        entries = _read_dirent_tree(
            fp,
            vol.partition_offset,
            vol.root_sector,
            vol.root_size,
            "",
            compute_hash=not args.no_hash,
        )
        entries.sort(key=lambda e: e.path.lower())

        xbe_files = [e.path for e in entries if not e.is_dir and e.path.lower().endswith(".xbe")]
        total_bytes = sum(e.size for e in entries if not e.is_dir)

        print(f"Image:            {args.image}")
        print(f"Format:           {vol.format_type} (partition offset {vol.partition_offset:#x})")
        print(f"Root Table:       sector {vol.root_sector}, {vol.root_size} bytes")
        print(f"Files / Dirs:     {sum(not e.is_dir for e in entries)} files, {sum(e.is_dir for e in entries)} dirs ({total_bytes:,} bytes)")
        print(f"XBE Executables:  {', '.join(xbe_files) if xbe_files else 'None'}")

        if args.extract is not None:
            stats = extract_entries(fp, vol, entries, args.extract, read_only=not args.writable)
            print(f"Extracted:        {stats['files']} files, {stats['dirs']} dirs ({stats['bytes']:,} bytes) -> {args.extract}")

        if args.manifest is not None:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "image": str(args.image),
                "image_size": file_size,
                "volume": asdict(vol),
                "xbe_files": xbe_files,
                "entries": [asdict(e) for e in entries],
            }
            args.manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Manifest written: {args.manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
