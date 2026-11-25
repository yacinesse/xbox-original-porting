#!/usr/bin/env python3
"""Verify a compiled Windows Original Xbox PC port release against shipping gates.

Performs automated, stdlib-only checks (zero pip or external binutils required):
  1. PE32/PE32+ Import Table Audit: flags any non-OS runtime DLLs (e.g.,
     libwinpthread-1.dll, libgcc_s_seh-1.dll, libstdc++-6.dll, ucrt/vcruntime
     dev DLLs) so standalone Windows Explorer launches never fail with missing DLLs.
  2. PE TLS Directory Audit: inspects DataDirectory[9] (.tls) to verify whether
     Win64 PE TLS callbacks (RECOMP_FAST_TLS) are linked into the binary.
  3. Optional Object / Symbol Audit: scans build .obj files for MinGW
     `__emutls_get_address` symbols (detects RECOMP_FAST_TLS regressions).
  4. Optional Clean Explorer Launch Simulation (`--test-explorer`): launches the
     executable from C:\\Windows\\Temp with PATH stripped strictly to Windows
     System32/Windows and all RECOMP_* overrides cleared (except timed exit),
     draining stdout/stderr asynchronously to avoid Win32 pipe deadlocks.
  5. Optional Disc Manifest Verification (`--manifest`): verifies read-only
     extracted files (default.xbe or full manifest) still match original SHA-256.
  6. Optional Repo Hygiene Scan (`--repo`): flags forbidden commercial assets
     or generated binaries/dumps that should stay out of Git.

Usage:
    py -3 verify_port_release.py path/to/game_port.exe
    py -3 verify_port_release.py build/recomp/game.exe --test-explorer 12 --manifest reports/disc-manifest.json --extracted private/extracted/disc
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

# Stock Windows system DLL prefixes/names allowed in a zero-dependency Win64 port.
ALLOWED_OS_DLLS: Set[str] = {
    "advapi32.dll",
    "avrt.dll",
    "bcrypt.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "d3d11.dll",
    "d3d12.dll",
    "d3dcompiler_47.dll",
    "dbghelp.dll",
    "dinput8.dll",
    "dsound.dll",
    "dwmapi.dll",
    "dxgi.dll",
    "gdi32.dll",
    "hid.dll",
    "imm32.dll",
    "iphlpapi.dll",
    "kernel32.dll",
    "kernelbase.dll",
    "mfplat.dll",
    "mfreadwrite.dll",
    "mmdevapi.dll",
    "msvcrt.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "opengl32.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "setupapi.dll",
    "shell32.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "user32.dll",
    "version.dll",
    "winmm.dll",
    "ws2_32.dll",
    "xaudio2_8.dll",
    "xaudio2_9.dll",
    "xinput1_4.dll",
    "xinput9_1_0.dll",
}

ALLOWED_OS_PREFIXES: Tuple[str, ...] = (
    "api-ms-win-",
    "ext-ms-win-",
)

FORBIDDEN_REPO_EXTS: Set[str] = {
    ".iso",
    ".xiso",
    ".xbe",
    ".xpr",
    ".xwb",
    ".xsb",
    ".xmv",
    ".bik",
    ".wma",
    ".exe",
    ".pdb",
    ".dmp",
    ".bmp",
    ".log",
}

IGNORED_DIRS: Set[str] = {
    ".git",
    "build",
    "out",
    "private",
    "saves",
    "game",
    "extracted",
    "assets",
    "__pycache__",
}


def rva_to_file_offset(rva: int, sections: Sequence[Tuple[int, int, int, int]]) -> Optional[int]:
    """Translate a PE RVA to a raw file offset using (vaddr, vsize, raw_ptr, raw_size)."""
    for vaddr, vsize, raw_ptr, raw_size in sections:
        span = max(vsize, raw_size)
        if vaddr <= rva < vaddr + span:
            off = raw_ptr + (rva - vaddr)
            if off < raw_ptr + raw_size:
                return off
    return None


def read_cstr(buf: bytes, off: int, max_len: int = 260) -> str:
    """Read a null-terminated ASCII string safely from a byte buffer."""
    if off < 0 or off >= len(buf):
        return ""
    end = buf.find(b"\x00", off, min(len(buf), off + max_len))
    if end < 0:
        end = min(len(buf), off + max_len)
    return buf[off:end].decode("ascii", errors="replace")


def parse_pe_metadata(exe_path: Path) -> Dict[str, object]:
    """Parse PE32/PE32+ header, imports, subsystem, and TLS directory using stdlib only."""
    data = exe_path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError(f"{exe_path} is not a valid PE (missing MZ header)")

    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 24 > len(data) or data[pe_off : pe_off + 4] != b"PE\x00\x00":
        raise ValueError(f"{exe_path} is missing PE signature at 0x{pe_off:X}")

    machine, num_sections, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", data, pe_off + 4)
    opt_off = pe_off + 24
    magic = struct.unpack_from("<H", data, opt_off)[0]
    is_pe64 = magic == 0x20B
    if magic not in (0x10B, 0x20B):
        raise ValueError(f"Unsupported PE optional header magic 0x{magic:04X}")

    subsystem = struct.unpack_from("<H", data, opt_off + 68)[0]
    dd_off = opt_off + (112 if is_pe64 else 96)
    num_rvas = struct.unpack_from("<I", data, opt_off + (108 if is_pe64 else 92))[0]

    def get_dd(idx: int) -> Tuple[int, int]:
        if idx >= num_rvas or dd_off + (idx + 1) * 8 > len(data):
            return 0, 0
        return struct.unpack_from("<II", data, dd_off + idx * 8)

    imp_rva, imp_size = get_dd(1)
    tls_rva, tls_size = get_dd(9)

    sec_off = opt_off + opt_size
    sections: List[Tuple[int, int, int, int]] = []
    section_names: List[str] = []
    for i in range(num_sections):
        off = sec_off + i * 40
        if off + 40 > len(data):
            break
        name = data[off : off + 8].rstrip(b"\x00").decode("ascii", errors="replace")
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((vaddr, vsize, raw_ptr, raw_size))
        section_names.append(name)

    imports: List[str] = []
    if imp_rva:
        imp_file_off = rva_to_file_offset(imp_rva, sections)
        if imp_file_off is not None:
            pos = imp_file_off
            while pos + 20 <= len(data):
                orig_thunk, ts, fwd, name_rva, first_thunk = struct.unpack_from("<IIIII", data, pos)
                if orig_thunk == 0 and ts == 0 and fwd == 0 and name_rva == 0 and first_thunk == 0:
                    break
                name_off = rva_to_file_offset(name_rva, sections)
                if name_off is not None:
                    dll = read_cstr(data, name_off)
                    if dll:
                        imports.append(dll)
                pos += 20

    non_os_dlls = [
        dll
        for dll in imports
        if dll.lower() not in ALLOWED_OS_DLLS
        and not any(dll.lower().startswith(pfx) for pfx in ALLOWED_OS_PREFIXES)
    ]

    return {
        "file": str(exe_path),
        "size_bytes": len(data),
        "arch": "x64 (PE32+)" if is_pe64 else f"PE32 (machine=0x{machine:04X})",
        "subsystem": "WINDOWS_GUI" if subsystem == 2 else ("WINDOWS_CUI" if subsystem == 3 else f"0x{subsystem:X}"),
        "sections": section_names,
        "imports": sorted(set(imports), key=str.lower),
        "non_os_dlls": sorted(set(non_os_dlls), key=str.lower),
        "has_pe_tls_directory": bool(tls_rva and tls_size),
        "tls_rva": f"0x{tls_rva:08X}",
        "tls_size": tls_size,
    }


def scan_objs_for_emutls(obj_dir: Path) -> Tuple[int, List[str]]:
    """Scan .obj files under obj_dir for `__emutls_get_address` symbol references."""
    needle = b"__emutls_get_address"
    scanned = 0
    hits: List[str] = []
    for p in sorted(obj_dir.rglob("*.obj")):
        scanned += 1
        try:
            if needle in p.read_bytes():
                hits.append(str(p.relative_to(obj_dir)))
        except OSError:
            continue
    return scanned, hits


def simulate_explorer_launch(exe_path: Path, seconds: int) -> Dict[str, object]:
    """Launch exe from C:\\Windows\\Temp with PATH stripped of MinGW/dev tools."""
    cwd = Path(r"C:\Windows\Temp") if os.name == "nt" and Path(r"C:\Windows\Temp").is_dir() else Path.cwd()
    clean_env: Dict[str, str] = {}
    for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "COMSPEC"):
        if k in os.environ:
            clean_env[k] = os.environ[k]
    clean_env["PATH"] = r"C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem"
    clean_env["RECOMP_EXIT_AFTER_SECS"] = str(seconds)

    # subprocess.communicate() drains stdout and stderr concurrently (no Win32 pipe deadlock).
    proc = subprocess.Popen(
        [str(exe_path.resolve())],
        cwd=str(cwd),
        env=clean_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    timeout = max(seconds + 20, 30)
    try:
        out_b, err_b = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        proc.kill()
        out_b, err_b = proc.communicate()
        timed_out = True

    stderr_text = err_b.decode("utf-8", errors="replace")
    stdout_text = out_b.decode("utf-8", errors="replace")
    combined = stdout_text + "\n" + stderr_text

    fast_tls_ok = "[FAST-TLS]" in combined and "verified" in combined
    crash_hits = [
        line.strip()
        for line in combined.splitlines()
        if any(tok in line for tok in ("ACCESS_VIOLATION", "FATAL:", "EXCEPTION_", "Unhandled exception"))
    ]
    return {
        "cwd": str(cwd),
        "path_env": clean_env["PATH"],
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "fast_tls_verified": fast_tls_ok,
        "crash_lines": crash_hits[:10],
        "stderr_tail": stderr_text.splitlines()[-15:],
    }


def verify_manifest(manifest_path: Path, extracted_root: Path, full_hash: bool) -> Dict[str, object]:
    """Verify SHA-256 of default.xbe (or all entries if full_hash=True) against disc-manifest.json."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries") or manifest.get("files") or []
    checked = 0
    mismatches: List[str] = []
    missing: List[str] = []

    for item in entries:
        if item.get("is_dir"):
            continue
        rel = str(item.get("path", "")).lstrip("/\\")
        expected = item.get("sha256")
        if not expected:
            continue
        if not full_hash and rel.lower() != "default.xbe":
            continue
        target = extracted_root / Path(rel)
        if not target.is_file():
            missing.append(rel)
            continue
        h = hashlib.sha256()
        with target.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        checked += 1
        if h.hexdigest().lower() != expected.lower():
            mismatches.append(f"{rel} (expected {expected}, got {h.hexdigest()})")

    return {
        "checked": checked,
        "missing": missing,
        "mismatches": mismatches,
        "passed": checked > 0 and not missing and not mismatches,
    }


def scan_repo_hygiene(repo_root: Path) -> List[str]:
    """Find commercial/generated files sitting outside ignored directories."""
    violations: List[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not (d.lower() == "external" and Path(root).name.lower() == "tools")]
        for fn in files:
            p = Path(root) / fn
            if p.suffix.lower() in FORBIDDEN_REPO_EXTS:
                violations.append(str(p.relative_to(repo_root)))
    return sorted(violations)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a compiled Windows Original Xbox PC port release.")
    parser.add_argument("exe", type=Path, help="Path to compiled Windows .exe")
    parser.add_argument("--obj-dir", type=Path, help="Optional CMake build dir to scan .obj files for __emutls_get_address")
    parser.add_argument("--test-explorer", type=int, default=0, metavar="SECS", help="Run clean Explorer launch simulation for SECS seconds")
    parser.add_argument("--manifest", type=Path, help="Path to reports/disc-manifest.json for asset integrity verification")
    parser.add_argument("--extracted", type=Path, help="Path to read-only extracted disc directory (required with --manifest)")
    parser.add_argument("--full-hash", action="store_true", help="Hash every file in --manifest instead of just default.xbe")
    parser.add_argument("--repo", type=Path, help="Scan workspace for unignored commercial/generated asset violations")
    parser.add_argument("--json", type=Path, help="Write structured audit report to JSON file")
    args = parser.parse_args(argv)

    failed = False
    report: Dict[str, object] = {}

    pe = parse_pe_metadata(args.exe)
    report["pe"] = pe
    print(f"[PE] {pe['file']} ({pe['size_bytes']:,} B, {pe['arch']}, {pe['subsystem']})")
    print(f"[PE] Imports: {len(pe['imports'])} DLLs | Non-OS DLLs: {len(pe['non_os_dlls'])}")
    if pe["non_os_dlls"]:
        print(f"  FAIL: Non-OS DLL imports detected: {', '.join(pe['non_os_dlls'])}")
        print("        Fix (MinGW): add `-static -static-libgcc` to CMake target_link_options.")
        failed = True
    else:
        print("  PASS: 0 non-OS DLL dependencies (standalone Explorer-ready).")

    print(f"[PE] TLS Directory (.tls): {'PRESENT' if pe['has_pe_tls_directory'] else 'ABSENT'} ({pe['tls_rva']}, {pe['tls_size']} B)")

    if args.obj_dir:
        scanned, hits = scan_objs_for_emutls(args.obj_dir)
        report["emutls_scan"] = {"scanned_objs": scanned, "hits": hits}
        print(f"[TLS] Scanned {scanned} .obj files for __emutls_get_address: {len(hits)} hit(s)")
        if hits:
            print(f"  WARN: Emulated TLS still referenced in: {', '.join(hits[:10])}")

    if args.test_explorer > 0:
        print(f"[EXPLORER] Simulating clean launch from C:\\Windows\\Temp for {args.test_explorer}s...")
        res = simulate_explorer_launch(args.exe, args.test_explorer)
        report["explorer_launch"] = res
        ok = (res["exit_code"] == 0) and (not res["timed_out"]) and (not res["crash_lines"])
        print(
            f"  {'PASS' if ok else 'FAIL'}: exit={res['exit_code']} timed_out={res['timed_out']} "
            f"fast_tls={res['fast_tls_verified']} crashes={len(res['crash_lines'])}"
        )
        if not ok:
            failed = True
            for ln in res["crash_lines"]:
                print(f"    CRASH: {ln}")

    if args.manifest:
        if not args.extracted:
            parser.error("--extracted is required when using --manifest")
        mres = verify_manifest(args.manifest, args.extracted, args.full_hash)
        report["manifest"] = mres
        print(
            f"[INTEGRITY] Checked {mres['checked']} file(s): "
            f"{'PASS' if mres['passed'] else 'FAIL'} (missing={len(mres['missing'])}, mismatches={len(mres['mismatches'])})"
        )
        if not mres["passed"]:
            failed = True

    if args.repo:
        viols = scan_repo_hygiene(args.repo)
        report["repo_hygiene"] = {"violations": viols}
        print(f"[HYGIENE] Non-ignored commercial/generated files: {len(viols)}")
        if viols:
            for v in viols[:15]:
                print(f"  WARN: {v}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"[REPORT] Wrote {args.json}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
