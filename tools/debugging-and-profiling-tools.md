# Tool Guide: Debugging, Capture & Profiling Tools

## 1. Live Hang & Spin-Loop Triage (`gdb --batch` on MinGW / VS on MSVC)

When `juiced_recomp.exe` or any recompiled port hits `0.00 fps` or stops advancing flips:

```powershell
# Poll process ID and dump every thread backtrace cleanly in one non-interactive command
gdb -p <PID> --batch -ex "set pagination off" -ex "thread apply all bt"
```

- **What to inspect:**
  - Thread 1 (`guest_main` / WinMain guest thread): If stuck in `sub_XXXXXXXX`, correlate `sub_XXXXXXXX` directly with `Source/Recompiled/recomp_*.c` and `functions.json`!
  - Check whether NV2A ack / VBlank threads are healthy or deadlocked on a critical section / KEVENT.
- **Built-in Watchdog:** Run with `RECOMP_WATCHDOG_SECS=25` so `xbox_kernel` prints the stalled guest PC, registers (`EAX..EDI`, `ESP`), and recent calls automatically after `N` seconds of zero progress.

## 2. Profiler & Differential Verification Switches (`xboxrecomp`)

- **`RECOMP_D3D11_PROF=1` + `RECOMP_PB_REPORT_MS=2000`:** Prints per-window breakdown of pushbuffer scan (`pb`), raster batch prep (`rbp`), vertex shader (`vsh`), `s_vcache` hits, `srv`/`vb`/`cb`/`api`/`present` times, and guest vs ack thread CPU ms.
- **`RECOMP_PB_SCAN=1`:** Read-only survey ranking every unhandled NV2A PGRAPH method (`0x0000`–`0x1FFF`) used by the title so you only implement methods the game actually issues.
- **`RECOMP_VSH_CHECK=1`:** Runs every vertex shader invocation through both the reference field interpreter and the Win64 SSE2 JIT (`nv2a_vsh_interp.c`), aborting/logging bit-exact hexadecimal float mismatches (`[VSH-DIFF]`). Keep active during smoke tests until reaching millions of `runs identical`.

## 3. RenderDoc & Per-Render-Target Frame Capture

- **Differential Frame Comparison:** Launch both `xemu` (OpenGL) and your native port (D3D11/D3D12) under **RenderDoc** at the same deterministic checkpoint (title menu, start grid). Inspect:
  1. Vertex shader outputs vs viewport (`pos.x/y`, `w`, AA scale).
  2. Bound SRVs (confirm offscreen RTs unbind cleanly before reuse as RTV).
  3. Blend state / `control0` W-buffer depth / `RSSetScissorRects` (`clip_x`, `clip_y`).
- **Diagnostic BMP Dumps:** Dumping individual offscreen render targets (`s_rts[]`) alongside the final presented backbuffer quickly reveals whether a HUD element (minimap, bloom buffer, AA resolve target) failed to draw or simply failed to composite onto the backbuffer.

## 4. `x64dbg` & MSVC `.map` / DbgHelp Correlation

- Build MSVC ports with `/MAP` (`GenerateMapFile`) or MinGW ports with `-g` debug info so host crash offsets (`+0x...` from module base) map 1:1 to `sub_XXXXXXXX`.
- Enable Windows D3D11 Debug Layer (`D3D11_CREATE_DEVICE_DEBUG`) during graphics bring-up, then turn off for release FPS benchmarking.
