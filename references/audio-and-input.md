# Audio, Video & Input Subsystems

This reference covers Original Xbox DirectSound8, MCPX APU (`0xFEC00000`), FMV playback (`Bink` & `XMV`), OHCI USB (`0xFED00000`), and PC keyboard/controller input translation.

## 1. Audio (`DirectSound8` & `MCPX APU`)

Original Xbox audio uses a statically linked `DSOUND` library (with optional 3D spatialization, Dolby `DOLBY` AC-3, `WMADEC`, and `XACT` soundbanks) backed by the NVIDIA **MCPX APU** (`0xFEC00000`, 256 hardware voices + programmable GP/EP DSPs).

### Implementation Strategies
1. **High-Level HLE (`DSOUND` API Replacement):**
   - Intercept `DirectSoundCreate`, `IDirectSound8`, `IDirectSoundBuffer8`, and `IDirectSoundStream`, routing to **XAudio2** or **SDL3 Audio**. Best when `DSOUND` signatures match cleanly without heavy inlined MMIO polling.
2. **MCPX APU Low-Level Emulation (`xbox_apu` *[VERIFIED]*):**
   - Required when statically linked `DSOUND` writes directly to `0xFEC00000+` MMIO registers via VEH trapping (`xbox_VehMmioFault`).
   - Enable `RECOMP_AC97_READY=1` so guest codec probes succeed immediately.
   - **APU Spin-Loop Hazard:** Watch for statically lifted `DSOUND` routines polling MMIO bits (e.g., `0xFEC0010B & 2`) or calling `KeStallExecutionProcessor` in GP DSP watchdog waits (`10 ms` per-frame stall). Patch unbounded loops with a bounded MMIO re-read in `recomp_manual.c` and short-circuit verified DSP watchdog stalls.
   - *(License note: upstream `xemu` APU extractions carry `LGPL-2.1+`—audit licenses before distribution.)*

### Xbox Audio Codecs & A/V Sync
- **PCM:** Uncompressed 8/16-bit signed little-endian.
- **Xbox ADPCM:** IMA ADPCM variant using **36-byte blocks per 64 samples** (per channel), decoded cleanly by FFmpeg (`adpcm_ima_xbox`) and `vgmstream`.
- **WMA / XACT (`.xwb` / `.xsb`):** Parse headers with bounds-checked readers; lifted `WMADEC` and `XACTENG` sections execute natively inside `xboxrecomp` ports.
- **A/V Synchronization:** Drive audio and video clocks from monotonic host time rather than rendered FPS so uncapped `Present` never speeds up cutscenes or sound effects.

## 2. Full-Motion Video (`Bink` vs `XMV`)

- **Bink Video (`.bik`):** Extremely common Xbox middleware.
  - **Key Finding *[VERIFIED]*:** Under full static recompilation (`xboxrecomp`), lifting all **`BINK*` code sections** alongside `DSOUND` and pushbuffer execution lets games play `.bik` intro/attract videos natively into `YUY2` textures with synchronized audio (`60+ FPS` / real-time). Note that D3D11 texture caches MUST hash guest `YUY2` texture memory per frame to detect in-place movie frame updates!
- **XMV (`.xmv`):** Microsoft's Xbox Media Video (WMV2/WMA2 container).
  - **Options:** Decode via `xbox_video` (Windows Media Foundation on `xboxrecomp`) / clean-room FFmpeg integration (audit LGPL/GPL), or keep an offline local-only `ffmpeg` script to transcode user-owned `.xmv`/`.bik` files to `.mp4` as a fallback.

## 3. Input (`XPP` / `XAPI` / `OHCI` → PC Keyboard & Controllers)

Original Xbox games poll controllers through `XPP`/`XAPI` (`XInitDevices`, `XInputOpen`, `XInputGetState`, `XInputSetState`), which talk directly to **MCPX OHCI USB controllers** (`0xFED00000`).

### Bring-Up Checklist *[VERIFIED]*
1. Call **`xbox_OhciInit()`** during startup and route MMIO via `xbox_VehMmioFault(ep)`.
2. Set `RECOMP_USB=1` and `RECOMP_KEYBOARD=1` if using keyboard input.

### Original Xbox Hardware Mapping Quirks
- **8-Bit Analog Face Buttons (`0..255`):** Unlike Xbox 360/One/Series XInput where `A/B/X/Y` are 1-bit flags, Original Xbox face buttons (`A`, `B`, `X`, `Y`, `Black`, `White`) return **8-bit analog pressure (`0–255`)** inside `bAnalogButtons[]`! Racing, fighting, and stealth games check `> threshold` (returns of `1` fail!). Always write **`255` (`0xFF`)** when a digital button is pressed and `0` when released.
- **Black & White Buttons:** Map cleanly to `LB` / `RB` on modern controllers (`xboxrecomp` `input_map.h`).
- **Rumble:** Map 16-bit `wLeftMotorSpeed` / `wRightMotorSpeed` to `XInputSetState` or `SDL_RumbleGamepad`.

### Genre-Appropriate Keyboard & Multi-Controller Support
- **Watch Out for Generic Keyboard Defaults:** `xboxrecomp`'s stock keyboard table (`input_map.h`) binds `WASD` to `LSTICK` and **Right Trigger (`RTRIGGER`) to key `'3'`**! For **racing games** (where `RTRIGGER` is throttle), this makes `'3'` accelerate while `'W'` does nothing in-race. Override default key bindings by genre (`W`/`Up` → `RTRIGGER`, `S`/`Down` → `LTRIGGER`, `A`/`D` → steering) or expose user-remappable `.ini` config via `xbox_InputMap_BindingsParse`.
- **Gamepad API Status:** Windows `XInput` covers up to 4 standard Xbox 360/One/Series pads; **SDL3 (`SDL_Gamepad`)** *[THEORETICAL / RECOMMENDED FOR MULTI-VENDOR]* supports Xbox, PlayStation, Switch, and hotplugging uniformly, whereas DirectInput/HID fallback is needed if legacy wheels/non-XInput USB pads must work under a pure-Win32 build.
