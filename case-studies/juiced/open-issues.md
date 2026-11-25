# *Juiced* Case Study: Remaining Open Issues & Resolved History

Per strict evidence rules, items in Section 1 are genuinely **[UNRESOLVED]** and must NOT be cited as complete in *Juiced*. Section 2 records previously open items that have since been **[VERIFIED]** solved.

## 1. Remaining Open / Untested Items ([UNRESOLVED])

### Unimplemented Minor Primitive Types
- **Observed Status:** In `nv2a_pb_exec.c`'s `raster_batch_program`, `NV_PRIM_POINTS` (e.g., particles/sparks — observed ~36 calls in trace) and `NV_PRIM_LINE_STRIP` (e.g., wireframe/debug/effects — observed ~24 calls in trace) fall into `default: break;` and are skipped.
- **Impact:** Minor particle or line effects are invisible until lowered into screen-space quads/triangles or native D3D11 point/line topologies.

### Full-Game & Platform Coverage Boundaries
- **Full Career Playthrough & Multi-Track Matrix:** Live verification covered boot, Bink intro FMVs, title screen, profile creation/reload (`Player`), crew logo, Arcade Novice Series, 3D Mitsubishi FTO showroom, and high-speed nitro/drift racing in San Ricardo & Engstrom District; a 100% manual playthrough across every career event, pink-slip race, and mod shop screen remains untested.
- **Non-XInput Wheels / DirectInput Controllers:** XInput gamepads + custom racing keyboard (`juiced_controls.ini`) are verified; DirectInput/HID steering wheels and PlayStation/Switch pads would require an SDL3 `SDL_Gamepad` layer.
- **Xbox Live (`XONLINE` / `XNET`):** No multiplayer or Xbox Live matchmaking flows have been tested.

## 2. Previously Open Issues Now Solved ([VERIFIED])

| Previously Open Issue | Verified Root Cause & Resolution |
|---|---|
| **Fullscreen Dark Vignette / Radial Motion Blur Fan** *(SOLVED)* | Juiced's radial motion blur fan (`prim=7`) self-samples the **currently active RT (`t->offset == cur_rt_va`)**, which previously skipped the GPU RT pool and read zeroed guest RAM (`0x00000000`), blending solid black around the viewport. Resolved via lazy GPU-to-GPU `CopyResource` RT snapshots (`copy_tex`/`copy_srv`, dirty-tracked by `write_seq`); visually verified clean outward-streaking radial blur at 105–119 MPH with nitro and drift. |
| **Intuitive Racing Keyboard Controls + INI Remapping** *(SOLVED)* | Verified exact `DRIVER1` & `UI` Xbox mappings from `scripts.dat`, implemented `keyboard.c` + `input_map.c` mapping `W`/`S` → Right/Left Trigger, `A`/`D` → Left Stick X, `Space` → `A` (`0xFF`), `Left Shift` → `Y` (Nitrous), `Enter`/`Esc` → `Start`, `Alt+Enter`/`F11` fullscreen, `F12` screenshot, merged with XInput gamepads and `juiced_controls.ini` overrides. |
| **`UDATA`/`TDATA` Profile Save Persistence** *(SOLVED)* | Created `Player` profile in-game -> persisted `saves/UDATA/545100ef/B36B6776DA41/{juicey.dat (51,049 B), SaveMeta.xbx, saveimage.xbx, signature (20 B)}` with 0 crashes in `sub_0001BE80`, and verified clean reload (`NTSTATUS 0x00000000`) across subsequent launches. |
| **Hot-Path Diagnostic Log Cleanup** *(SOLVED)* | Gated `[READ]` behind `RECOMP_LOG_READ` and `[GPU] draw #` behind `RECOMP_PB_EXEC_VERBOSE`; zero-DLL standalone `-static -static-libgcc` executable verified cleanly from `C:\Windows\Temp` with stripped `PATH`. |
