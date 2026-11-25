# Graphics & Rendering (`D3D8` & `NV2A` → Modern PC)

This reference covers translating the Original Xbox's Direct3D 8 and NVIDIA NV2A GPU pipeline to modern Windows graphics APIs (`Direct3D 11` / `Direct3D 12` / `Vulkan`), including critical hardware details proven during live `D3D8LTCG` bring-up.

## 1. Primary Architecture: D3D8 HLE vs. NV2A Pushbuffer Execution

Choose based on your `default.xbe` symbol/LTCG analysis (never guess):

1. **NV2A Pushbuffer / PGRAPH Execution *[VERIFIED for `D3D8LTCG`]***:
   - Essential when statically linked `D3D8LTCG` inlines device calls or uses register calling conventions so API-level HLE misses draw setup.
   - Intercepts NV2A pushbuffer writes & MMIO (`0xFD000000`) (`RECOMP_PB_EXEC=1`), decodes vertex streams + VSH/FFP transforms + state registers (`nv2a_pb_exec.c`), and routes batches through a hardware **`Nv2aBackend` (D3D11)** (`nv2a_backend.h`).
   - **Critical Rule:** Do **not** rely on CPU pixel software rasterization beyond initial bring-up (`~15–20 FPS` ceiling). Keep offscreen render targets on the GPU as Direct3D 11 `Texture2D` / `RTV` / `SRV` objects with zero CPU readback.
2. **D3D8 High-Level Emulation (HLE) *[Preferred when XDK D3D8 matches ≥ 90%]***:
   - Identify `IDirect3DDevice8` / `D3DDevice_*` functions cleanly (`XbSymbolDatabase` / `xbe_symbols`) and route to D3D11 (fastest bring-up) or D3D12 (`XboxXBERecomp` style).

## 2. Critical NV2A Hardware Semantics & D3D11 Translation Details

### Register Combiners (`ps_shade`)
- Xbox extends PC D3D8 with **NV2A Register Combiners** (`D3DRS_PSCOMBINERCOUNT`, 8 general stages `color_icw`/`alpha_icw`/`color_ocw`/`alpha_ocw`/`factor0`/`factor1`, plus final combiner `final0`/`final1`/`fog`).
- **D3D11 Strategy *[VERIFIED]*:** Either pass `CombinerCB` constants to a dynamic HLSL stage-loop evaluator (supports all `0..8` stages + `dot`/mux/shift-bias ops + final `D + C*(1-A) + B*A` blend with zero shader-compile hitching!) OR hash the combiner state to compile per-permutation HLSL shaders.
- **Extended Backend Structs:** Upstream `nv2a_backend.h` started with stage 0 + diffuse only; extend `Nv2aBatch` and `Nv2aVertex` to carry **`textures[4]`**, `specular`, `fog`, and `t[4][3]` (`u, v, q` / cubemap vector) for authentic multi-texturing.

### Supersampled Anti-Aliased Surfaces (`2×` / `2×2`) & Active RT Extent
- Games enable supersampled offscreen RTs (e.g., `640×960` pre-resolve RT resolving to `640×480` backbuffer, flagged in `SET_SURFACE_FORMAT` bits 12–15) and may transiently touch a display surface with `clip_h = 960` before later full-origin frames draw `640×480`.
- Scale transformed vertex shader positions by `s_gpu.aa_sx` / `s_gpu.aa_sy`, clamp near-zero `w` (`fabsf(pos[3]) < 1e-6f`), and separate **allocated capacity (`alloc_w`, `alloc_h`)** from **active draw extent (`active_w`, `active_h`)** per `GpuRT`. Pass `(active_w/alloc_w, active_h/alloc_h)` UV scale to `ps_blit`, crop BMP dumps via `CopySubresourceRegion`, and scale RT-as-SRV UVs by `(1/alloc_w, 1/alloc_h)` for linear RTs and `(t->w/alloc_w, t->h/alloc_h)` for normalized RTs.

### Sub-Clip Scissor Rectangles (`clip_x`, `clip_y`) — Minimaps & Split Viewports
- Games draw circular minimaps, mirrors, and corner UI panels by setting NV2A surface clip offsets (`clip_x`, `clip_y`, `width`, `height`, e.g., `112×112+56+324`) while keeping the **same** base RT VA!
- Pass `clip_x, clip_y` through `Nv2aSurface` from NV2A `SET_SURFACE_CLIP_HORIZONTAL` / `VERTICAL`, preserve the matching full-size RT when `clip_x || clip_y != 0`, and call `RSSetScissorRects` (`left=clip_x, top=clip_y, right=clip_x+width, bottom=clip_y+height`) with `ScissorEnable = TRUE`. Ignoring `clip_x`/`clip_y` causes corner viewports to vanish or stretch full-screen!

### Logarithmic W-Buffering (`SET_CONTROL0 & 0x10000`)
- Xbox titles frequently switch between Z-buffering and **perspective W-buffering** (`SET_CONTROL0` bit 16). Linear Z depth fails badly under W-buffer passes (causing distant tracks/sky to clip HUD or near geometry).
- Expose `control0` in `Nv2aRenderState`; when `(control0 & 0x10000u)` and depth test/write are active, route to a dedicated pixel shader (`ps_main_wbuf`) outputting `SV_Depth` computed logarithmically from `noperspective` interpolated `1/w` (`w = 1.0f / max(p_rhw, 1e-9f)`).

### Vertex Shaders (136-Bit NV2A Microcode & SSE2 JIT)
- Supports paired MAC + ILU execution per 136-bit slot (remember: when paired with any MAC op, ILU **always** writes `R1`, NOT `tdst`!).
- Clamp near-infinite/denormal `rhw` safely in HLSL (`1e-9f..1e9f`) and **validate any Win64 SSE2 VSH JIT differentially with `RECOMP_VSH_CHECK=1`** to catch input/output register aliasing (such as `jit_ilu_lit`).

### Triangle Strip Winding & Remaining Primitives
- Enable **`RECOMP_STRIP_ALT_WINDING=1`** so odd triangles in `NV_PRIM_TRIANGLE_STRIP` flip `(i+1, i)` cleanly for D3D11 culling hardware. Also note NV2A evaluates face culling from projected screen positions.
- Track unhandled primitives: `NV_PRIM_POINTS` and `NV_PRIM_LINE_STRIP` are skipped in default rasterizer loops unless explicitly emitted as quads or point/line draw topologies.

### Textures, Swizzling, Palettes, Cubemaps & Render-Target Hazards
- **Morton Swizzling vs Linear vs DXT:** Most Xbox textures (except `D3DFMT_LIN_*` and `YUY2`/`UYVY`) are Morton Z-order swizzled; `DXT1`/`3`/`5` are block-linear.
- **Palettized `P8` (`fmt 0x0B`):** Decode 256-entry CLUT (`Nv2aTexture.palette`) and hash palette memory alongside texels so palette animations stay live.
- **6-Face Cubemaps (Dirty-Tracked):** Handle `cube` and `cube_face_stride` (`128`-byte NV2A face alignment). Dirty-track per-RT `write_seq` vs per-cubemap `cube_face_seq[6]` in `sync_cube_rt_faces` so faces only `CopySubresourceRegion` when re-rendered (`193 → 3` copies/frame), and verify identical format & dimensions before copying.
- **Guest RAM Coherency (Bink Video / Dynamic Textures):** Titles decode `YUY2` video frames or dynamic textures in-place at the same RAM `offset`. Hash sample texels cleanly per flip (`checked_flip`) and re-upload on hash change.
- **Texture Cache Sizing, Hashing & SRV Lifetime Safety:** Use a **`512 × 8`** set-associative texture cache with **multiplicative Fibonacci hashing** (avoids 2048-byte aligned DXT5 set collisions), gate lookups by `rs->rc.stage_program` (`modes 1..3`), canonicalize unused `palette`/`pitch` key fields, replace `last_used_flip` LRU with a **monotonic `uint64_t use_seq`**, and pin staged `srvs[0..3]` with `AddRef()`/`Release()` across `PSSetShaderResources` to prevent same-draw driver crashes (`nvwgf2umx.dll`). Key DSVs by `(zeta_va, w, h)` (`MAX_DSVS = 32`).
- **D3D11 RTV/SRV Hazard & Active RT Self-Sampling (Radial Motion Blur / Feedback):**
  1. Explicitly bind `NULL` across PS SRV slots `0..7` before `OMSetRenderTargets`.
  2. When a post-processing pass (radial motion blur, feedback trails) samples the **currently bound RT (`t->offset == cur_rt_va`)**, do **NOT** fall through to zeroed guest RAM (which causes a black vignette!). Instead maintain a lazy GPU snapshot (`copy_tex`/`copy_srv`, dirty-tracked via `write_seq`/`copy_seq`), run GPU-to-GPU `CopyResource(copy_tex, cur_rt->tex)` when dirty, and bind `copy_srv`.

## 3. Capture-Based Validation

- Compare **RenderDoc** captures on your native D3D11/D3D12 port and **`xemu`** (OpenGL) at identical checkpoints:
  - Bound VBs, projection/viewport matrices, AA scale, and `clip_x`/`clip_y` scissor rects
  - Unswizzled/decoded textures and blend factor states (`0x8003`/`0x8004` constant factor vs alpha!)
  - Backbuffer + intermediate offscreen RT `.bmp` dumps.
