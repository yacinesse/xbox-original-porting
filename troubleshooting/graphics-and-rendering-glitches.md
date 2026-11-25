# Troubleshooting: Graphics, Shaders & Rendering Glitches

## 1. Quarter-Screen / Top-Half Cropped Rendering (Supersampled AA & Transient RT Growth)

- **Symptom:** The rendered frame only occupies the top half (`640×480` inside `640×960`) or corner (`1/4`) of the window, or a `640×480` backbuffer squishes vertically after a `640×960` / `1280×960` AA surface is touched.
- **Root Cause:** Xbox titles enable NV2A supersampling (`2×` vertical `640×960`, or `2×2` `1280×960`), and may transiently touch a display surface (e.g., `0x81104000`) with `clip_h = 960` before later full-origin frames draw `640×480`. If the RT cache grows `alloc_h` to `960` without tracking active draw extent, `ps_blit`, BMP dumps, and RT-as-SRV sampling stretch or crop the frame.
- **Verified Fix:**
  1. Scale vertex shader output `pos[0]` / `pos[1]` by `s_gpu.aa_sx` / `s_gpu.aa_sy` (`SET_SURFACE_FORMAT` bits 12–15).
  2. Track **`active_w`, `active_h`** separately from allocated texture dimensions (`alloc_w`, `alloc_h`) per `GpuRT`, updating `active_w`/`active_h` on full-origin (`clip_x == 0 && clip_y == 0`) clears/draws.
  3. Pass `(active_w / alloc_w, active_h / alloc_h)` UV scale to `ps_blit` (`ClearCB`), crop `dump_rt_bmp` via `CopySubresourceRegion`, and compute RT-as-SRV UV scale as `(1/alloc_w, 1/alloc_h)` for unnormalized linear RTs and `(t->w/alloc_w, t->h/alloc_h)` for normalized RTs.

## 2. Sky, Walls, or Track Geometry Clipping Foreground HUD

- **Symptom:** Far geometry draws in front of closer cars, walls, or HUD elements, or depth sorting collapses at medium/far range.
- **Root Cause:** Many Xbox titles use NV2A **W-buffering** (`SET_CONTROL0` bit 16, `control0 & 0x10000u`) rather than hyperbolic Z-buffering (`z/w`). A standard D3D11 pixel shader outputting default `SV_Position.z` compares linear Z against W-buffered expectations.
- **Verified Fix:** Pass `control0` in `Nv2aRenderState`. When `(control0 & 0x10000u)` and depth test/write are enabled, select a W-buffer pixel shader (`ps_main_wbuf`) computing depth from `noperspective` interpolated `1/w` (`w = 1.0f / max(p_rhw, 1e-9f)`) encoded logarithmically into `[0, 1)`.

## 3. Missing Minimap, Radar, or Corner UI Viewports

- **Symptom:** HUD panels or circular minimaps draw at full screen, get clipped off, or vanish entirely.
- **Root Cause:** The game selects a sub-clip rectangle inside the same surface (`clip_x`, `clip_y`, `width`, `height`, e.g., `112×112+56+324`), but the backend ignores `clip_x`/`clip_y` and sets scissor rects to `(0, 0, w, h)` or indexes the RT table purely by `va` + `(clip_w, clip_h)`.
- **Verified Fix:**
  1. Pass `clip_x` and `clip_y` through `Nv2aSurface` from NV2A `SET_SURFACE_CLIP_*` registers.
  2. Look up existing full-size offscreen RTs matching `va` even when `clip_x || clip_y` is non-zero (`alloc_w >= clip_x + width`).
  3. Issue `RSSetScissorRects` with `(clip_x, clip_y, clip_x + width, clip_y + height)` and enable `ScissorEnable = TRUE` on D3D11 rasterizer states.

## 4. Inside-Out / Missing Strip Faces

- **Symptom:** Every second triangle in triangle-strip meshes (roads, cars, UI ribbons) is invisible or back-lit.
- **Root Cause:** `nv2a_pb_exec` stock path emits `(i, i+1, i+2)` for every triangle strip index without reversing odd triangles.
- **Verified Fix:** Enable `RECOMP_STRIP_ALT_WINDING=1`. Also emulate NV2A culling from **projected screen positions** when post-clip triangles wrap behind the eye.

## 5. Black Screen, Static Bink FMV, or D3D11 Hazard Warnings

| Symptom | Cause | Fix |
|---|---|---|
| Bink `.bik` video stays stuck on frame 1 | Guest updates the same linear/YUY2 guest RAM address in-place without changing buffer `offset` | Hash guest texture memory (rate-limited per draw/flip) in `get_texture_srv` and re-upload on hash change |
| D3D11 debug warning: *resource still bound on input* | Offscreen RT previously bound as `SRV` is now bound as `RTV` | Explicitly bind `NULL` to PS SRV slots `0..7` before `OMSetRenderTargets` |
| Flat/white or missing multi-textured surfaces | Backend only reads texture stage 0 and ignores NV2A register combiners / cubemaps / `0x0B` CLUT palettes | Extend `Nv2aBatch` with `textures[4]`, `palette`, `cube`, `cube_face_stride`, and compile an HLSL combiner interpreter |
| Missing sparks / radar dots / lines | `raster_batch_program` skips `NV_PRIM_POINTS` and `NV_PRIM_LINE_STRIP` | Lower points/lines into screen-space quads or emit D3D11 point/line-strip draw calls |

## 6. GPU Driver Access Violation (`nvwgf2umx.dll`) on First Heavy 3D Frame

- **Symptom:** Menus and 2D screens work cleanly, then the first complex 3D gameplay frame (`rts >= 16`) triggers an access violation inside the GPU driver (`nvwgf2umx.dll+0x...`, `fault=0x10` read) during `PSSetShaderResources` or `Draw`.
- **Root Cause:** **Same-draw SRV use-after-free** in a small 4-way texture cache using coarse `last_used_flip` LRU! When two active texture stages on the same draw hash into the same set and all 4 ways already share `last_used_flip == s_d3d.flips`, stage `k` evicts and `Release()`s the SRV that stage `0..k-1` just stored in `srvs[]` before `PSSetShaderResources` executes. Secondary crash sources include mismatched DSV sizes (`zeta_va` reused at different dimensions) and unguarded cubemap `CopySubresourceRegion` calls.
- **Verified Fix:**
  1. Expand texture cache to **`512 × 8 = 4,096`** ways and switch RT/DSV/texture LRU from `last_used_flip` to a **monotonic `uint64_t use_seq`** incremented on every lookup.
  2. Pin every non-NULL SRV placed into `srvs[0..3]` with **`AddRef()`**, call `PSSetShaderResources`, and **`Release()`** after binding so an eviction inside the same draw can never free a staged SRV.
  3. Key `GpuDSV` by **`(zeta_va, w, h)`** (`MAX_DSVS = 32`), raise state cache caps (`MAX_BLEND/DEPTH/SAMPLERS = 256`), and verify identical `DXGI_FORMAT` and dimensions before cubemap `CopySubresourceRegion`.

## 7. Post-Processing Dark Vignette / Black Radial Motion Blur Fan (*SOLVED*)

- **Symptom:** High-speed radial motion blur, zoom blur, or feedback-trail passes (`NV_PRIM_TRIANGLE_FAN`, `prim=7`) darken the screen perimeter into a black vignette instead of streaking the scene outward.
- **Root Cause:** The game binds the **currently active render target** (`t->offset == cur_rt_va`) as a texture input (`SRV`) while drawing back into that same RT. Because D3D11 forbids binding one `ID3D11Texture2D` simultaneously as RTV and SRV, skipping the GPU RT pool when `t->offset == cur_rt_va` falls through to guest RAM (`0x00000000` — untouched zeroed RAM!), blending solid black over the outer radial ring!
- **Verified Fix:**
  1. Add a lazy GPU snapshot texture + SRV (`copy_tex`, `copy_srv`) and monotonic counters (`write_seq`, `copy_seq`) to each `GpuRT`.
  2. Increment `cur_rt->write_seq` on every clear or draw into `cur_rt`.
  3. Whenever a texture stage requests `t->offset == cur_rt_va`, issue a fast GPU-to-GPU **`CopyResource(cur_rt->copy_tex, cur_rt->tex)`** (only when `cur_rt->copy_seq != cur_rt->write_seq`, then set `copy_seq = write_seq`) and bind `cur_rt->copy_srv`!
  - Zero CPU readback, zero D3D11 RTV/SRV hazard, and 100% authentic outward-streaking radial motion blur.
