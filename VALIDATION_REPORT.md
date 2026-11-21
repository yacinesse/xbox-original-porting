# Skill Validation Report

**Skill:** `xbox-original-porting` (`D:\AI Projects\XBOX ORIGINAL PC PORT\xbox-original-porting`)  
**Updated:** 2026-11-21  
**Baseline:** Original `xbox-original-porting` (28 files) + **Juiced (2005, Original Xbox) Porting Project** empirical findings and `sp00nznet/xboxrecomp` (`v0.17.0` fork) testing.

## 1. Summary of Expansion & Upgrades

- **Architecture & Decision-Gate Correction:** Shifted from assuming `XboxXBERecomp` / D3D8 API HLE (`>= 90%` match) fits most titles cleanly to documenting a dual-path decision rubric emphasizing `xboxrecomp` + NV2A pushbuffer execution (`RECOMP_PB_EXEC=1`, `RECOMP_PB_WALK=segment`) + hardware **D3D11 `Nv2aBackend`** for **`D3D8LTCG`** binaries, alongside an explicit warning against clean-room C++/D3D12 engine rewrites for authentic full-game ports.
- **Reorganized & Expanded Structure (`28 → 52` files):**
  - Added dedicated `troubleshooting/` playbooks (7 files), `tools/` CLI guides (4 files), `resources/` verified directory & reading index (2 files), buildable `examples/` (`recomp_main_template.c`, `recomp_manual_wrapper_example.c`, `CMakeLists.port.example`), `workflows/optimization.md`, and strictly separated `case-studies/juiced/` (5 files).
  - Added two new stdlib-only Python utilities in `scripts/`:
    - `scripts/scan_vtables.py` — Scans `.rdata`/`.data` pointer tables into `xboxrecomp` `--seed-functions` JSON while blocking interior mid-function split hazards (`--functions`).
    - `scripts/probe_containers.py` — Read-only container magic, entropy, chunked-zlib (`footer-table-archive` & `length-prefixed-zlib`), and ASCII preview inspector.
- **Technical Knowledge Added & Graded:** Documented verified fixes (`XbSymbolDatabaseCLI`, multi-section disassembly, `RECOMP_FAST_TLS` `%gs:` TEB slot, Win64 SSE2 VSH JIT + `RECOMP_VSH_CHECK=1`, `xbox_Nv2aMirrorFence`, `sub_00280CC7` / `0xFEC0010B` APU spin-loop, `0xFD100410` flip-hold, `0x0027A905` DSP wait, `ps_main_wbuf` logarithmic W-buffer, `640×960` AA resolve, `clip_x`/`clip_y` scissor rects for minimaps, `RECOMP_STRIP_ALT_WINDING=1`, Explorer CWD resolution), while isolating Juiced's remaining unresolved issues cleanly in `case-studies/juiced/open-issues.md`.

## 2. Post-Edit Verified Checks (Executed After Final Modifications)

All automated checks below were executed directly against the final updated files in `xbox-original-porting/`:

| Check / Tool | Scope & Command | Observed Result |
|---|---|---|
| **Python Syntax (`py_compile`)** | All 6 files in `scripts/` | Exit `0` (`init_port_db.py`, `probe_containers.py`, `scaffold_port.py`, `scan_vtables.py`, `xbe_inspect.py`, `xiso_inspect.py`) |
| **`scripts/xiso_inspect.py`** | Read-only inspect on retail Redump XGD1 `Game.iso` (`--no-hash`) | Exit `0`; detected `XGD1 (partition offset 0x18300000)`, `1807 files, 150 dirs`, `3` XBEs |
| **`scripts/xbe_inspect.py`** | Parsed retail `D3D8LTCG` `default.xbe` (`35` sections) | Exit `0`; decoded `TitleID=545100EF`, `Build=retail`, `Sections=35`, `KImports=150`, `Libs` including `D3D8LTCG` |
| **`scripts/scan_vtables.py`** | Scanned `.rdata`/`.data` with `--functions ... --strict-prologue` | Exit `0`; found `vtables=299`, `unique_targets=2158`, `known_skipped=2135`, `interior_blocked=4` (split protection!), `output_seeds=19` JSON |
| **`scripts/probe_containers.py`** | Tested recursively on retail `.wma`/`.xsb`/`.dat`/`.xbx` and `.zbg` samples | Exit `0`; classified `.dat` (`footer-table-archive`), `.xbx` (`XPR0`), `.xsb` (`SDBK`), `.wma` (`ASF/WMA`), and `.zbg` (`length-prefixed-zlib`) |
| **`scripts/scaffold_port.py` & `init_port_db.py`** | Scaffolded test project & populated SQLite DB from retail `xbe_info.json` | Exit `0`; created workspace tree + SQLite DB (`imports=150`, `functions=1`) |
| **C Example Syntax (`gcc -Wall -Wextra -fsyntax-only`)** | `kernel-override-example.c`, `recomp_manual_wrapper_example.c`, `recomp_main_template.c` (against `xboxrecomp` headers) | Exit `0` across all 3 C files |
| **Markdown Link Integrity** | All `41` `.md` files across `xbox-original-porting/` (`75` relative links checked) | `0` broken links |
| **Asset Hygiene Check** | Recursive extension scan across `D:\AI Projects\XBOX ORIGINAL PC PORT` | `0` commercial binaries/assets present |

## 3. Experimental / Unresolved Boundaries (Not Claimed as Universally Solved)

- **Fullscreen Vignette / Radial Motion-Blur Fan (`[UNRESOLVED]` in *Juiced*):** Narrowed down to `NV_PRIM_TRIANGLE_FAN` (`prim=7`) backbuffer/bloom passes; exact texture-address wrap vs blend-factor root cause remains open.
- **Minor Primitives (`NV_PRIM_POINTS`, `NV_PRIM_LINE_STRIP`):** Skipped in the tested `nv2a_pb_exec.c` path.
- **Genre Keyboard Remapping & Non-XInput Controller Fallback:** Stock `RECOMP_KEYBOARD` defaults (`'3'` throttle) and multi-slot XInput/DirectInput/HID racing presets are documented with design rules, not yet runtime-tested in *Juiced*.
- **Full-Game Career Saves & Xbox Live (`XONLINE`):** Only early boot/menu/race slices were runtime-verified; multi-XBE transitions, full playthroughs, and Xbox Live emulation remain unverified.
- **Non-Windows Hosts & Ghidra MCP Bake-Off:** Linux/macOS (`SDL2`/`OpenGL`) `xboxrecomp` targets and Ghidra MCP bridges (`REA`/`ReVa`) were not benchmarked on host in this project.
