# Troubleshooting: Input, Controller & Audio Issues

## 1. Unexpected Default Keyboard Controls (e.g. `'3'` Instead of `'W'` to Accelerate)

- **Symptom:** Menu navigation or driving requires unintuitive keys (such as pressing `'3'` to move forward while `'W'` does nothing or moves camera/menus).
- **Root Cause:** Generic `RECOMP_KEYBOARD` presets map `W/A/S/D` to the **Xbox Left Analog Stick** (`LSTICK_UP/DOWN/LEFT/RIGHT`) and map `RTRIGGER` / `LTRIGGER` to keys like `'3'` / `'1'` or `Q`/`E`. In racing games and many shooters, throttle/shoot is bound to **Right Trigger (`RTRIGGER`)**, not Left Stick Y!
- **Fix:** Provide a configurable key map (e.g., via `input_map.h` / `.ini` / CMake option) with **genre-aware defaults**:
  - **Action / Third-Person / FPS:** `WASD` → Left Stick, Arrow keys / Mouse → Right Stick, triggers on Mouse1/2 or `E`/`Q`.
  - **Racing:** `W` / `Up` → `RTRIGGER` (Accelerate), `S` / `Down` → `LTRIGGER` or Brake button, `A`/`D` or `Left`/`Right` → `LSTICK_LEFT`/`RIGHT`.

## 2. Game Does Not Respond to Keyboard or Xbox Controller

- **Symptom:** Title reaches `PRESS START` screen, but neither keyboard nor plugged-in gamepad advances past it.
- **Root Causes & Checklist:**
  1. Missing **`xbox_OhciInit()`**: Titles that statically link `XAPILIB`/`XPP` poll USB OHCI controllers (`0xFED00000`) rather than calling a hooked `XInputGetState` symbol.
  2. Missing **`xbox_VehMmioFault(ep)`** in the Vectored Exception Handler: OHCI MMIO reads trap silently or crash if the VEH doesn't dispatch them.
  3. Missing `RECOMP_USB=1` / `RECOMP_KEYBOARD=1` environment variables.
  4. **Digital vs. Analog Face Buttons (`0..255`):** Original Xbox `A`, `B`, `X`, `Y`, `Black`, `White` return `0–255` pressure bytes (`bAnalogButtons[]`). Returning `1` instead of `255` (`0xFF`) fails game pressure thresholds!
  5. **Non-XInput Controllers:** Standard `XInputGetState` only sees Xbox 360/One/Series XInput devices; older DirectInput wheels/pads or PlayStation/Switch pads require SDL3 (`SDL_Gamepad`) or DirectInput/HID translation *(note: SDL3 `SDL_Gamepad` handles cross-vendor mapping automatically when integrated).*

## 3. Silent Audio, Crackling, or Bink Audio Stalls

- **Missing MCPX Init Flags:** Ensure `RECOMP_AC97_READY=1` is active for titles polling AC97 codec readiness.
- **Uncapped FPS Speeding Up Audio/Cutscenes:** Never tie `KeQueryPerformanceCounter` or `rdtsc` advancement to variable unlocked frame counts; pace clocks against real monotonic host time (`QueryPerformanceCounter`).
- **APU MMIO / DSP Watchdog Deadlocks:** See [freezes-and-deadlocks.md](freezes-and-deadlocks.md#signature-d-mcpx-apu-mmio-spin-loop-0xfec0010b--dsound).
