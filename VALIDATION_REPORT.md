# Skill Validation Report

**Skill:** `xbox-original-porting`  
**Updated:** 2026-11-24  
**Baseline:** `xbox-original-porting` (52 files) upgraded with all verified advanced tools, templates, and empirical findings from completing the end-to-end native Windows x64 static recompilation port of **Juiced (2005, Original Xbox, TitleID `545100EF`)** (`build/recomp/juiced_recomp.exe`, GCC 16.2.0 `-O3 -DRECOMP_FAST_TLS=1 -static -static-libgcc`).

## 1. Summary of Expansion & Upgrades (`52 → 56` files)

- **2 New Stdlib-Only Python Tools (`scripts/`):**
  - `scripts/verify_port_release.py` — Pure-Python PE32/PE32+ import auditor (verifying **0 non-OS DLLs** such as `libwinpthread-1.dll`), PE `.tls` DataDirectory[9] checker, `.obj` `__emutls_get_address` regression scanner, clean Windows Explorer launch simulator (`C:\Windows\Temp`, `PATH` stripped to `System32`/`Windows`, deadlock-free async stdout/stderr), `disc-manifest.json` SHA-256 verifier, and repo hygiene scanner.
  - `scripts/analyze_d3d11_prof.py` — `[D3D11-PROF]` log parser & bottleneck diagnostician generating Markdown FPS tables across `2D Menus / FMV`, `Light 3D / Showroom`, and `Heavy 3D Gameplay`, automatically flagging aligned texture cache hash collisions, redundant cubemap face syncs, active RT self-sampling passes, and guest/VSH CPU bottlenecks.
- **Hardened `scripts/scaffold_port.py`:** Extended `.gitignore` template to also ignore `Game/`, `saves/`, `tools/external/`, `*.exe`, `*.bmp`, `*.png`, and `*.log`.
- **New & Upgraded C / Build Templates (`examples/`):**
  - `examples/recomp_fast_tls.h` — Production-ready Win64 PE64 `.CRT$XLB` TEB-slot TLS (`gs:[0x1480 + slot * 8]`) register header + callback implementation with `r_`-prefixed struct members (preventing `#define eax g_eax` macro expansion), `_tls_used` linker anchor, and runtime `recomp_fast_tls_verify_init()`.
  - `examples/CMakeLists.port.example` — Added `-static -static-libgcc` (eliminating `libwinpthread-1.dll` on Explorer launches) and `PORT_ENABLE_FAST_TLS` (`-DRECOMP_FAST_TLS=1`).
  - `examples/recomp_main_template.c` — Added `recomp_fast_tls_verify_init()`, `RECOMP_VBLANK=1`, `SymFromAddr` + `CaptureStackBackTrace` non-MMIO AV diagnostics inside safe VEH, `RECOMP_EXIT_AFTER_SECS` automated smoke-test exit hook (flushing `stdout`/`stderr`), and `saves\` auto-resolution.
- **New Advanced Tool Guide (`tools/rea-and-advanced-tools.md`):** Documented `verify_port_release.py`, `analyze_d3d11_prof.py`, `rea` MCP reverse-engineering workflows (respecting Mandatory Rule #2's `medium` confidence cap), and Win32 `-mwindows` PowerShell automation pitfalls (pipe deadlocks, `Start-Process -Wait`, absolute dump paths).
- **Critical Verified Root Causes Added Across `troubleshooting/`, `references/`, `workflows/`, and `case-studies/juiced/`:**
  1. **Radial Motion Blur / Dark Vignette SOLVED:** Active RT self-sampling (`t->offset == cur_rt_va`) fell through to zeroed guest RAM; solved via dirty-tracked GPU-to-GPU `CopyResource` RT snapshots (`copy_tex`/`copy_srv`).
  2. **`640×960` vs `640×480` Active RT Extent & RT-as-SRV UV Scaling:** Separate `active_w`/`active_h` from `alloc_w`/`alloc_h` for `ps_blit`, BMP dumps, and linear/normalized RT-as-SRV UVs.
  3. **NVIDIA `nvwgf2umx.dll` Multi-RT Crash:** Same-draw SRV use-after-free in 4-way cache; fixed via `512×8` cache, monotonic `uint64_t use_seq` LRU, `AddRef`/`Release` SRV pinning across `PSSetShaderResources`, `(zeta_va,w,h)` DSV keying, and cubemap `CopySubresourceRegion` guards.
  4. **Texture Cache Hash Collisions on 2048-Byte Aligned DXT5 Textures (>30× speedup):** Multiplicative Fibonacci hash + `rc.stage_program` gating (`modes 1..3`) + canonicalized `eff_pal`/`eff_pitch` dropped `miss` from `~180 → 0` and `tex` from `3.5–4.7 ms → 0.12–0.15 ms`.
  5. **Dirty-Tracked Dynamic Cubemap Face Sync:** `write_seq` vs `cube_face_seq[6]` cut copies from `193 → 3`/frame.
  6. **Win64 SSE2 VSH JIT + `FastAttrStream` + `nv2a_vsh_input_mask()`:** Passed `RECOMP_VSH_CHECK=1` with **67,108,864 identical runs, 0 divergences** (plus `<math.h>` `j1` collision warning).
  7. **Cold-Boot Title `KEVENT` Race Under `-O3`:** Hardened `ke_guest_event_prepare()` with `volatile uint32_t *` + `MemoryBarrier()`.
  8. **MinGW `libwinpthread-1.dll` Static Linking Trap:** `-static -static-libgcc` required instead of `-Wl,-Bstatic -lwinpthread`.
  9. **Juiced Case Study Updated:** Moved Radial Motion Blur Vignette, Racing Keyboard + `juiced_controls.ini` + XInput merge, and `UDATA` Save Persistence (`juicey.dat` 51,049 B create+reload) from `[UNRESOLVED]` to `[VERIFIED]`.

## 2. Post-Edit Verified Checks (Executed After Final Modifications)

| Check / Tool | Scope & Command | Observed Result |
|---|---|---|
| **Python Syntax (`py_compile`)** | All `8` scripts in `scripts/` | Exit `0` (`analyze_d3d11_prof.py`, `init_port_db.py`, `probe_containers.py`, `scaffold_port.py`, `scan_vtables.py`, `verify_port_release.py`, `xbe_inspect.py`, `xiso_inspect.py`) |
| **`scripts/verify_port_release.py`** | Live audit on `build/recomp/juiced_recomp.exe` (`--obj-dir`, `--test-explorer 8`, `--manifest`, `--extracted`, `--repo`) | Exit `0`; **0 non-OS DLLs** (24 stock OS DLLs), PE `.tls` PRESENT, **0 `__emutls_get_address`** across 18 `.obj`s, Explorer launch from `C:\Windows\Temp` with stripped `PATH` PASS (`exit=0`, `fast_tls=True`, `crashes=0`), `default.xbe` SHA-256 PASS, 0 repo hygiene violations |
| **`scripts/analyze_d3d11_prof.py`** | Live parse of 42 `[D3D11-PROF]` samples from `Juiced` unlocked benchmark (`--markdown`) | Exit `0`; accurately bucketed `2D Menus / FMV` (med `647.0 FPS`), `Light 3D / Showroom` (`319.0 FPS`), `Heavy 3D Gameplay` (med `73.0 FPS`, max `78.0 FPS`, `miss=0`, `tex=0.14ms`, `cube=3`, `self_max=5`) |
| **C Template Syntax (`gcc -Wall -Wextra -fsyntax-only`)** | `examples/recomp_fast_tls.h` (header + `RECOMP_FAST_TLS_IMPLEMENTATION`), `examples/recomp_main_template.c` (both `-DRECOMP_FAST_TLS=1` and default), `examples/kernel-override-example.c`, `examples/recomp_manual_wrapper_example.c` | Exit `0` across all 4 C/H templates in both TLS modes |
| **Markdown Link Integrity** | All `42` `.md` files across `xbox-original-porting/` (`82` relative links checked) | `0` broken links |
| **Skill Asset Hygiene Check** | Recursive extension scan across `xbox-original-porting/` | `0` commercial binaries/assets present |

## 3. Remaining Open Boundaries (Honest Scope)

- **Minor NV2A Primitives (`NV_PRIM_POINTS`, `NV_PRIM_LINE_STRIP`):** Still skipped in default `nv2a_pb_exec.c` raster batch loops unless lowered to quads or native point/line draw topologies.
- **Non-XInput Wheels / DirectInput Controllers:** XInput + configurable keyboard INI is verified; DirectInput/HID wheels and PlayStation/Switch pads remain design guidance (SDL3 `SDL_Gamepad`) until runtime-tested.
- **Full Career Playthrough & Xbox Live (`XONLINE`/`XNET`):** Automated & interactive validation covered boot, FMVs, menus, profile creation/reload, showroom, and live 3D racing; full career progression and Xbox Live networking remain untested.
- **Non-Windows Hosts (Linux/macOS):** Workflows and Win64 PE TLS / D3D11 templates target Windows x64 first.
