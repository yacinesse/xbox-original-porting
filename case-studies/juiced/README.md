# Case Study: *Juiced* (2005, Original Xbox) → Native Windows PC

> **Purpose:** Preserve Juiced-specific reverse-engineering discoveries, bring-up bugs, performance optimizations, and unresolved edge cases separately from the game-agnostic core skill. Every claim below is explicitly tagged by verification status.

## Status Legend

- **[VERIFIED]** Directly reproduced, measured in build/runtime logs, or confirmed in captured screenshots/differential checks.
- **[EXPERIMENTAL]** Observed working in constrained test runs (e.g., scripted menus/single tracks), lacking full-game regression coverage.
- **[UNRESOLVED]** Investigated and narrowed down, or designed in code/docs, but not yet fixed or runtime-verified.

## 1. Project Summary & Architectural Pivot

| Attribute | Value / Finding | Evidence Status |
|---|---|---|
| **Title / ID** | *Juiced* (`545100EF`, THQ / Juice Games, 2005) | [VERIFIED] |
| **Disc Format** | XGD1 Redump (`7,825,162,240` B), XDVDFS partition at `0x18300000` (`1,807` files, `150` dirs, `1.9746 GiB`) | [VERIFIED] |
| **Executable** | `default.xbe` (`3,518,464` B, `35` sections, Retail XOR keys, Base `0x00010000`, Entry `0x001AF14A`) | [VERIFIED] |
| **XDK & Graphics** | XDK `1.0.5849` with **`D3D8LTCG`** (Link-Time Code Generation), `DSOUND`, `XACTENLT`, `XONLINES`, `BINK*` | [VERIFIED] |
| **Final Strategy** | `xboxrecomp` (`v0.17.0` fork) static x86→C + `XbSymbolDatabase` (`449` symbols) + Custom **D3D11 NV2A pushbuffer backend** | [VERIFIED] |
| **Compiler / Build** | CMake + Ninja + WinLibs MinGW-w64 GCC (`-O3 -fno-math-errno`) | [VERIFIED] |

### Critical Lesson: Why Clean-Room C++/D3D12 Was Abandoned

1. **Initial Experiment (Clean-Room C++20 / D3D12):** Attempted to reimplement vehicle physics, UI, and rendering cleanly from extracted `.dat`/`.zbg`/`.dds`/script files. Resulted only in placeholder geometry (`row_major float4x4` matrix transpose bugs and missing authentic menus/track shaders/UI state machines).
2. **Pivot to Static Recompilation (`xboxrecomp`):** Because `default.xbe` used **`D3D8LTCG`**, standard D3D8 API hooking could not cover inlined pushbuffer emission cleanly. Lifting all code sections (`--all`) and registering a hardware **Direct3D 11 backend** behind `nv2a_backend.h` preserved 100% of original menus, Bink intro FMVs, UI layout, audio, vehicle physics, and race state.

## 2. Case-Study Index

- [executable-and-assets.md](executable-and-assets.md) — XGD1 layout, XBE sections, `XbSymbolDatabase` symbol recovery, `.dat` chunked-zlib & `.xbx` forensics.
- [bringup-and-fixes.md](bringup-and-fixes.md) — From boot crashes and `0.00 fps` stalls (`D3D8LTCG` fence mirror, `RECOMP_PB_WALK`, `sub_00280CC7`, mid-instruction splits, CWD bug) to playable rendering.
- [graphics-and-optimization.md](graphics-and-optimization.md) — Hardware D3D11 NV2A backend, AA supersampling (`640x960`), W-buffer shader, sub-clip minimap scissor fix, and the **17 FPS → 98–128 FPS** optimization campaign (`RECOMP_FAST_TLS`, Win64 SSE2 VSH JIT + `16,777,216` parity checks).
- [open-issues.md](open-issues.md) — Explicitly tracked unresolved glitches, unimplemented primitives (`POINTS` / `LINE_STRIP`), racing keyboard bindings (`'3'` throttle vs `'W'`), and multi-slot controller work.
