# *Juiced* Case Study: Graphics Pipeline & Performance (`17 FPS → 98–128 FPS`)

This document summarizes verified rendering fixes and measured CPU/GPU performance optimizations in `RecompPort/src/nv2a_d3d11_backend.c` and the forked `xboxrecomp` runtime.

## 1. Graphics Bring-Up & Bug Fixes ([VERIFIED])

| Issue | Root Cause | Fix & Verification |
|---|---|---|
| **CPU Rasterizer Too Slow (~15 FPS)** | Software pixel + register-combiner rasterizer in `nv2a_pb_exec.c` took `~67 ms/frame` | Implemented hardware D3D11 `Nv2aBackend` (`nv2a_d3d11_backend.c`); GPU-resident RTs (`MAX_RTS = 48`) eliminate CPU readbacks |
| **Cropped / Quarter-Screen Image** | Juiced renders pre-resolve supersampled AA surface `0x015B4000` at **`640×960`** before resolving to **`640×480`** (`0x01104000` / `0x01230000`) | Added `s_gpu.aa_sx` / `s_gpu.aa_sy` scaling and `fabsf(pos[3]) < 1e-6f` clamping after VSH JIT execution; D3D11 RT pool tracks logical vs pitch/alloc dimensions |
| **Sky & Track Clipping HUD** | Juiced enables NV2A perspective W-buffer (`SET_CONTROL0` bit 16, `control0 & 0x10000u`); linear Z comparison failed | Exposed `control0` in `Nv2aRenderState`; added `ps_main_wbuf` writing logarithmic `SV_Depth` (`(log2(max(w, 0.0009765625f)) + 10.0f) / 34.0f * 0.999999f`) with `noperspective p_rhw` |
| **Missing Bottom-Left Circular Minimap** | Minimap renders to sub-clip rect **`112×112+56+324`** on `0x815B4000`, but `Nv2aSurface` did not pass `clip_x` / `clip_y` and D3D11 reset scissor/extent to `(0, 0)` | Added `clip_x, clip_y` to `Nv2aSurface`, populated from `s_gpu.clip_x, s_gpu.clip_y`, and applied `RSSetScissorRects` (`clip_x..clip_x+width`) in `d3d11_draw`. Verified visually in `shot_minimap_ok.bmp` |
| **Inverted Strip Culling / Holes** | `nv2a_pb_exec.c` emitted `(i, i+1, i+2)` for every strip triangle, inverting odd faces | Enabled `RECOMP_STRIP_ALT_WINDING=1` so odd strip triangles swap `(i+1, i)` |
| **Multi-Stage Combiners & Bink Video** | Single-stage fixed pipeline missed Juiced car/track lighting, `0x0B` CLUT palettes, 6-face cubemaps, and live `YUY2` Bink frames | Added `Nv2aTexture textures[4]`, `palette`, `cube`, `cube_face_stride`, full 8-stage + final combiner HLSL evaluator (`ps_shade`), and guest RAM hash checking to re-upload mutated Bink frames |
| **D3D11 Hazard Warnings** | Binding an offscreen RT as an SRV while still bound as RTV | Explicitly unbind SRV slots `0..7` (`NULL`) before `OMSetRenderTargets` |

## 2. Performance Campaign (`17 FPS → 98–128 FPS` Race / `4,500+ FPS` Menus) ([VERIFIED])

Measured with `RECOMP_PRESENT_VSYNC=0` on live San Ricardo / Engstrom District races and menu flows:

| Optimization | Problem Identified | Measured Gain / Outcome |
|---|---|---|
| **Compiler Flags (`-O3 -fno-math-errno`)** | `src/kernel/CMakeLists.txt` built non-MSVC targets at `-O2` with `errno` math checks | Faster tight loops in VSH / pushbuffer / kernel code |
| **Skip Redundant CPU `zbuf_clear()`** | `NV097_CLEAR_SURFACE` (`0x1D94`) still zeroed ~5 MB software depth RAM every frame even when hardware `s_backend->clear` was registered | Eliminated multi-millisecond wasted RAM writes per frame |
| **`RECOMP_FAST_TLS` (`%gs:` TEB Slot)** | MinGW GCC/Clang compiled `__thread` registers (`g_eax..g_edi`, `g_xmm0..7`) into **`__emutls_get_address` function calls** on every register access | Replaced TLS vars on `_WIN64` GNU/Clang with single `TlsAlloc()` slot cached at TEB offset `g_recomp_tls_teb_off` (`movq %gs:(off), %r`); removed 100% of `__emutls_get_address` samples. Lifted live Engstrom District race from **56–60 FPS → 78–94 FPS** (combined with texture cache hashing) |
| **Win64 x86-64 SSE2 VSH JIT + `jit_ilu_lit` Fix** | Vertex shader interpreter took most of `rbp` time across millions of vertices | Dynamically JIT-compiles NV2A vertex microcode to native SSE2 x64 (`nv2a_vsh_prepare_jit`) with direct indexed `s_vcache` + `FastAttrStream` fetch. Fixed `jit_ilu_lit` input/output aliasing bug (`c == out`). **Differential Parity (`RECOMP_VSH_CHECK=1`):** **`16,777,216` identical runs**, `0` divergences |
| **Bulk Pushbuffer Dispatch** | Per-word call overhead for array elements, inline vertices, and VSH constants | Added `nv2a_pb_exec_array_elem16_bulk`, `array_elem32_bulk`, `inline_bulk`, and `vsh_const_bulk` in `nv2a_pb_scan.c` |
| **Syscall & Stderr Cleanup** | `draw_batch` called uncached `getenv()` per draw; `xbox_VblankAckHeld()` called `QPC` every tick; unbuffered `stderr` stalled threads; `DXGI` used older swap effect | Cached env lookups once; cached vblank tick with `GetTickCount()`; `64 KiB` `_IOFBF` `stderr`; `timeBeginPeriod(1)`; `DXGI_SWAP_EFFECT_FLIP_DISCARD` + tearing. Reached **98.0–128.0 FPS** in live races (`4,322–4,564 FPS` 2D menus, `340–406 FPS` pre-race) |
