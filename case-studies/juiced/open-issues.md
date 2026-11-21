# *Juiced* Case Study: Unresolved Issues & Incomplete Work

Per strict evidence rules, every item below is **[UNRESOLVED]** or **[EXPERIMENTAL / NOT YET IMPLEMENTED]** and must NOT be cited as fixed in *Juiced*.

## 1. Visual Glitches ([UNRESOLVED])

### Fullscreen Dark Vignette / Radial Motion Blur Fan
- **Observed Symptom:** User reported a fullscreen vignette / dark edge artifact during driving.
- **Diagnostic Trace Status:** Narrowed down via `[FTRACE-FAN]` and multi-RT BMP dumps to `NV_PRIM_TRIANGLE_FAN` (`prim=7`, trace line `15782`) sampling backbuffer surface `0x81230000` (`addr=(3,3)`, `filter=02042000`) plus a bloom surface pass around `0x81B24800` (`line 15757`), before work shifted to skill extraction.
- **Root Cause:** Not yet confirmed. Suspected wrap/clamp border behavior, UV normalization near corners, or bloom/combiner alpha-blend factor mismatch when sampling a resolved `640×960` AA surface.

### Unimplemented Minor Primitive Types
- **Observed Status:** In `nv2a_pb_exec.c`'s `raster_batch_program`, `NV_PRIM_POINTS` (e.g., particles/sparks — observed ~36 calls in trace) and `NV_PRIM_LINE_STRIP` (e.g., wireframe/debug/effects — observed ~24 calls in trace) fall into `default: break;` and are skipped.
- **Impact:** Minor particle or line effects are invisible until lowered into screen-space quads/triangles or native D3D11 point/line topologies.

## 2. Input & Controller Support ([UNRESOLVED / WIP])

- **Default Keyboard Binding Issue:** Under `xboxrecomp`'s stock `RECOMP_KEYBOARD=1` mapping, Left Stick Up defaults to `'W'` while **Right Trigger (`RTRIGGER` — Juiced's throttle)** defaults to **`'3'`**! Users expecting `WASD` driving controls had to press `'3'` to accelerate.
- **Missing Multi-Slot XInput / Non-XInput Controller Work:** Intuitive racing keyboard presets (`W`/`Up` throttle, `S`/`Down` brake/reverse, `A`/`D` steering, mapped cleanly alongside XInput/DirectInput/HID pads) were designed as next steps, **not** implemented or runtime-tested yet.

## 3. Gameplay & Platform Coverage Gaps ([UNRESOLVED])

- **Menu Flow & FMVs:** Automated test runs verified boot, Bink intros, menu navigation, car select (`NEW DRIVER NAME`, `CHOOSE PHONE`), and live driving in San Ricardo / Engstrom District, **not** a complete manual interactive playthrough of all UI screens.
- **Saves (`TDATA`/`UDATA`) & Career Mode:** Early crash on `SAVING...` (`CMSGlobal.sav`) via `sub_0001BE80` was fixed, but end-to-end save/reload persistence across full career progression remains untested.
- **Xbox Live (`XONLINE` / `XNET`):** No multiplayer or Xbox Live matchmaking flows have been tested.
- **Clean-Up Needed in Working Fork:** Diagnostic logging flags (`[FTRACE*]`, `[BLOOM-*]`, per-RT dump instrumentation) remained in `JuicedPort`'s working tree during the vignette investigation.
