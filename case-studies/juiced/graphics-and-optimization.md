# *Juiced* Case Study: Graphics Pipeline & Performance

This document summarizes verified rendering fixes and measured CPU/GPU performance optimizations in `nv2a_d3d11_backend.c` and the `xboxrecomp` runtime across both the original reference bring-up and the 2026-11-24 end-to-end standalone port (`build/recomp/juiced_recomp.exe`, GCC 16.2.0 `-O3 -DRECOMP_FAST_TLS=1 -static -static-libgcc`).

## 1. Graphics Bring-Up & Bug Fixes ([VERIFIED])

| Issue | Root Cause | Fix & Verification |
|---|---|---|
| **CPU Rasterizer Too Slow (~15 FPS)** | Software pixel + register-combiner rasterizer in `nv2a_pb_exec.c` took `~67 ms/frame` | Implemented hardware D3D11 `Nv2aBackend` (`nv2a_d3d11_backend.c`); GPU-resident RTs (`MAX_RTS = 48`) eliminate CPU readbacks |
| **Cropped `640×960` vs `640×480` Frame** | Juiced renders pre-resolve supersampled AA surface `0x015B4000` at `640×960` and transiently grows display RT `0x81104000` `alloc_h` to `960` before drawing `640×480` | Added `aa_sx`/`aa_sy` scaling, `fabsf(pos[3]) < 1e-6f` clamping, per-`GpuRT` **`active_w`/`active_h`** tracking, UV-scaled `ps_blit` (`ClearCB`), `CopySubresourceRegion` BMP cropping, and RT-as-SRV UV scaling (`1/alloc_w,h` linear; `t->w/alloc_w,h` normalized) |
| **Sky & Track Clipping HUD** | Juiced enables NV2A perspective W-buffer (`SET_CONTROL0` bit 16, `control0 & 0x10000u`); linear Z comparison failed | Exposed `control0` in `Nv2aRenderState`; added `ps_main_wbuf` writing logarithmic `SV_Depth` (`(log2(max(w, 0.0009765625f)) + 10.0f) / 34.0f * 0.999999f`) with `noperspective p_rhw` |
| **Missing Bottom-Left Circular Minimap** | Minimap renders to sub-clip rect **`112×112+56+324`** on `0x815B4000`, but `Nv2aSurface` did not pass `clip_x`/`clip_y` | Added `clip_x, clip_y` to `Nv2aSurface`, preserved full-size RT lookup when `clip_x \|\| clip_y != 0`, and applied `RSSetScissorRects` (`clip_x..clip_x+width`) |
| **Inverted Strip Culling / Holes** | `nv2a_pb_exec.c` emitted `(i, i+1, i+2)` for every strip triangle, inverting odd faces | Enabled `RECOMP_STRIP_ALT_WINDING=1` so odd strip triangles swap `(i+1, i)` |
| **Multi-Stage Combiners & Bink Video** | Single-stage pipeline missed car/track lighting, `0x0B` CLUT palettes, 6-face cubemaps, and live `YUY2` Bink frames | Added `textures[4]`, `palette`, `cube`, `cube_face_stride`, full 8-stage + final combiner HLSL evaluator (`ps_shade`), and guest RAM hash checking for in-place Bink frames |
| **NVIDIA `nvwgf2umx.dll` Crash on First 3D Race Frame (`rts=23`)** | Same-draw SRV use-after-free when multiple stages hashed into the same 4-way set on the same flip (`last_used_flip` collision) | Expanded texture cache to **`512 × 8 = 4,096`**, switched LRU to monotonic `uint64_t use_seq`, pinned staged `srvs[]` with **`AddRef`/`Release`** across `PSSetShaderResources`, keyed `GpuDSV` by `(zeta_va, w, h)` (`MAX_DSVS = 32`), raised state caches to `256`, and guarded cubemap `CopySubresourceRegion` format/dims |
| **High-Speed Radial Motion Blur Dark Vignette *(SOLVED)*** | Radial blur fan (`prim=7`) self-samples active RT (`t->offset == cur_rt_va`), previously bypassing GPU RT pool and sampling zeroed guest RAM (solid black) | Added per-`GpuRT` lazy GPU snapshot (`copy_tex`/`copy_srv`, dirty-tracked via `write_seq`/`copy_seq`) using GPU-to-GPU **`CopyResource`**; visually verified clean outward-streaking radial blur at 105–119 MPH with nitro & drift |

## 2. Performance Campaign ([VERIFIED])

Measured with `RECOMP_PRESENT_VSYNC=0` on live San Ricardo 3D racing (`1,000+` draws, `130k–158k` verts/frame, dynamic cubemaps + radial motion blur, `rts=23`):

| Stage / Optimization | San Ricardo 3D Race | 3D FTO Showroom | Texture Lookup (`tex` / `miss`) | Key Mechanism |
|---|---:|---:|---|---|
| **Baseline** (D3D11 + interpreted VSH + MinGW `emutls` + colliding hash) | 21–34 FPS | 43 FPS | 3.5–4.7 ms (`~180`/frame) | Hardware D3D11 backend offloads CPU pixel rasterizer (`~15 FPS`) |
| **+ Win64 SSE2 VSH JIT + `FastAttrStream` + Dirty Cubemaps** | 41–50 FPS | 124 FPS | 3.5–4.7 ms (`~180`/frame) | Native SSE2 VSH JIT (`VirtualAlloc` RWX, 128-entry cache), `nv2a_vsh_input_mask()` skips unused attrs, dirty-tracked cubemap RT sync (`cube: 193 → 3`) |
| **+ `RECOMP_FAST_TLS=1` (PE `.CRT$XLB` TEB Slot) + Fibonacci Texture Hash** | **70–78 FPS** *(up to 98–128 FPS with bulk PB)* | **130–319 FPS** | **0.12–0.15 ms (`0` misses/frame)** | Eliminated 100% of `__emutls_get_address` refs (`gs:[0x1480 + slot * 8]`); multiplicative Fibonacci hash fixed 2048-byte DXT5 set collisions (`16/512 → 512/512` sets); gated lookups by `rc.stage_program` (`1..3`) & canonicalized `eff_pal`/`eff_pitch` |

- **2D Menus & Bink FMVs (unlocked):** **412–2,066 FPS** (VSync-capped to 60 FPS by default).
- **Mandatory VSH JIT Differential Gate (`RECOMP_VSH_CHECK=1`):** **`67,108,864` (67.1M) bit-for-bit identical vertex runs, `0` divergences** across menus, 3D FTO showroom, and San Ricardo nitro racing (exact `DP3`/`DPH`/`DP4` rounding order, exact `-0.0f`/`NaN` parity for `MIN`/`MAX`/`RCC`/`RCP`, non-aliasing C helpers for `ARL`/`EXP`/`LOG`/`LIT`).
