# Troubleshooting: Graphics, Shaders & Rendering Glitches

## 1. Quarter-Screen / Cropped Rendering (Supersampled AA Surfaces)

- **Symptom:** The rendered frame only occupies the top half or corner (`1/2` or `1/4`) of the window, or a `640×480` backbuffer crops against a `640×960` / `1280×960` surface.
- **Root Cause:** Xbox titles frequently enable NV2A supersampling (`2×` vertical `640×960`, or `2×2` `1280×960`), rendering 3D passes to an oversized offscreen surface while programming logical `640×480` viewports and later resolving/blitting to `640×480`.
- **Verified Fix:**
  1. Scale vertex shader output `pos[0]` / `pos[1]` by `s_gpu.aa_sx` / `s_gpu.aa_sy` (`SET_SURFACE_FORMAT` bits 12–15).
  2. Preserve logical `clip_w`/`clip_h` vs physical allocated surface pitch (`alloc_w`, `alloc_h`) in your D3D11 RT cache rather than truncating to logical 640×480 prematurely.

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
- **Verified Fix:** Enable `RECOMP_STRIP_ALT_WINDING=1`. Also remember to emulate NV2A culling from **projected screen positions** when post-clip triangles wrap behind the eye.

## 5. Black Screen, Static Bink FMV, or D3D11 Hazard Warnings

| Symptom | Cause | Fix |
|---|---|---|
| Bink `.bik` video stays stuck on frame 1 | Guest updates the same linear/YUY2 guest RAM address in-place without changing buffer `offset` | Hash guest texture memory (rate-limited per draw/flip) in `get_texture_srv` and re-upload on hash change |
| D3D11 debug warning: *resource still bound on input* | Offscreen RT previously bound as `SRV` is now bound as `RTV` | Explicitly bind `NULL` to PS SRV slots `0..7` before `OMSetRenderTargets` |
| Flat/white or missing multi-textured surfaces | Backend only reads texture stage 0 and ignores NV2A register combiners / cubemaps / `0x0B` CLUT palettes | Extend `Nv2aBatch` with `textures[4]`, `palette`, `cube`, `cube_face_stride`, and compile an HLSL combiner interpreter |
| Missing sparks / radar dots / lines | `raster_batch_program` skips `NV_PRIM_POINTS` and `NV_PRIM_LINE_STRIP` | Lower points/lines into screen-space quads or emit D3D11 point/line-strip draw calls |

## 6. Post-Processing Artifacts (Bloom / Radial Vignette Fans)

- **Symptom:** Screen corners darken excessively or radial blur passes obscure the viewport.
- **Diagnostic Workflow:** Enable targeted draw tracing (`[FTRACE]`) around fullscreen `NV_PRIM_TRIANGLE_FAN` (`prim=7`) and offscreen bloom RTs (`s_rt` dumps). Compare UV clamping/wrap modes (`addr_u`/`addr_v`), blend factor constants (`0x8003`/`0x8004` constant color vs alpha), and resolved `1×` vs `2×` AA RT UV scaling against `xemu` in RenderDoc. *(Marked **inconclusive/open** until verified per-title.)*
