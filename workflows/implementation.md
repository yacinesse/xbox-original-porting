# Workflow 5: Runtime Implementation (Incremental Bring-Up)

**Goal:** Wire host memory aliases, VEH MMIO traps, kernel/filesystem shims, hardware D3D11 pushbuffer graphics, audio, and intuitive PC input incrementally through Tier 0, Tier 1, and Tier 2.

## Principles
- **Incremental Bring-Up:** Boot → Memory/VEH/OHCI → Pushbuffer/Fence Advance → Hardware D3D11 Backend → Title Screen (`Tier 0`) → Playable Level (`Tier 1`) → Full Game & Saves (`Tier 2`).
- **No Silent No-Ops:** Unimplemented ordinals/methods must log (rate-limited) and count failures rather than silently corrupting state.

## Steps

1. **Executable Root & Host Startup Hygiene (`main.c`)**
   - Use [recomp_main_template.c](../examples/recomp_main_template.c): locate `default.xbe` & writable `saves\` relative to `GetModuleFileNameA` and call `SetCurrentDirectoryA(...)` so launching from Windows Explorer always finds game files.
   - Link MinGW-w64 builds with **`-static -static-libgcc`** ([CMakeLists.port.example](../examples/CMakeLists.port.example)) so zero non-OS DLLs (`libwinpthread-1.dll`) are imported.
   - Configure large buffered `stderr` (`setvbuf(..., _IOFBF, 65536)`), `timeBeginPeriod(1)`, and `RECOMP_VBLANK=1`.
   - Install Vectored Exception Handler delegating strictly to `xbox_VehMmioFault(ep)` (with `SymFromAddr` + `CaptureStackBackTrace` logging on unexpected non-MMIO AVs) — **never** swallow game `DIV0` or SEH faults.
2. **Memory, Kernel, OHCI & D3D8LTCG Fence Bring-Up**
   - Initialize `CreateFileMapping` mirror views (`xbox_MemoryLayoutInit()`), `D:`/`T:`/`U:`/`Z:` host paths, and USB OHCI (`xbox_OhciInit()`).
   - Configure safe defaults (unset env vars to turn off, never set `"0"` on presence flags):
     - `RECOMP_PB_EXEC=1`
     - `RECOMP_PB_WALK=segment` (avoid `dma` unless software `NO_OPERATION` interrupt delivery is implemented)
     - `RECOMP_FLIP_PACING=0` (prevents `0xFD100410` flip-hold stalls)
     - `RECOMP_AC97_READY=1`, `RECOMP_USB=1`, `RECOMP_KEYBOARD=1`
   - If using `D3D8LTCG`, extract `D3D8LTCG__D3D_g_pDevice` via `XbSymbolDatabaseCLI` and wire `xbox_Nv2aMirrorFence(g_pDevice_va, 0x2Cu, 0x30u)` (verifying offsets for your XDK build).
3. **Hardware Graphics Backend (`Nv2aBackend` / D3D11 or HLE)**
   - **Never ship the CPU software rasterizer** for playable gameplay (`~15 FPS` ceiling). Register a hardware **D3D11 `Nv2aBackend`** (`nv2a_backend_register`):
     - Track GPU-resident offscreen RTs (`MAX_RTS`), separating `alloc_w`/`alloc_h` (e.g., `640×960` supersampled AA targets) from `active_w`/`active_h` (`640×480`) for cropped `ps_blit`, BMP dumps, and RT-as-SRV UV scaling.
     - Scale transformed vertices by `aa_sx` / `aa_sy`.
     - Pass `control0` (`0x0290`) and select W-buffer depth output (`ps_main_wbuf` when `control0 & 0x10000u`).
     - Pass `Nv2aSurface.clip_x, clip_y` into `RSSetScissorRects` so sub-viewports (minimaps, split panels) render intact.
     - Enable `RECOMP_STRIP_ALT_WINDING=1`, unbind SRV slots `0..7` before `OMSetRenderTargets`, support **active RT self-sampling via GPU `CopyResource` snapshots (`copy_tex`/`copy_srv`)** for radial blur/feedback effects, use a `512×8` Fibonacci-hashed texture cache with monotonic `use_seq` LRU + `AddRef`/`Release` SRV pinning, key DSVs by `(zeta_va, w, h)`, dirty-track dynamic 6-face cubemap syncs, and hash guest RAM for in-place `YUY2` Bink video updates.
4. **Audio & Genre-Appropriate PC Controls**
   - Ensure MCPX APU (`xbox_apu` / `DSOUND`) handles AC97 readiness cleanly; patch any tight MMIO busy-waits (`0xFEC0010B`) or 10 ms DSP watchdog delays cleanly.
   - Wire both **XInput/SDL3 controller support** (mapping PC digital face buttons to `255` `0xFF` analog bytes!) and **intuitive genre-matched keyboard presets** (do NOT leave `RTRIGGER` on `'3'` for racing games — bind `W`/`Up` throttle, `S`/`Down` brake, `A`/`D` steering!).
5. **Saves (`TDATA`/`UDATA`), FMVs & Optimization**
   - Verify persistent save creation/reload, run native FMVs without `KeQueryPerformanceCounter` speedup, then execute [Workflow 8: Optimization](optimization.md).

## Exit Gate
- [ ] Tier 0 achieved: launches cleanly from both CLI and Explorer, reaches title screen, runs 10+ minutes.
- [ ] Tier 1 achieved: first playable level renders uncropped with correct depth/HUD/minimap, audio, and playable PC controls.
- [ ] `reports/port.db` updated with all overrides, kernel statuses, and verified fixes.
