# Workflow 6: Systematic Debugging, Hang Triage & Visual Diagnosis

**Goal:** Rapidly pinpoint freezes, `ICALL` crashes, mid-instruction splits, and NV2A rendering glitches using repeatable telemetry rather than blind guesswork.

## Steps

1. **Triage Crashes & Exceptions First**
   - Record minidump / exception address and offset from executable base (`addr - module_base`), matching it against MSVC `.map` or MinGW debug symbols (`gdb` / `addr2line`) to locate exact `sub_XXXXXXXX`.
   - Inspect the **ICALL trace ring buffer** (`g_icall_trace`) and recent `[KERNEL]`/`[FILE]` logs:
     - Outside code range (`0x400000..0xFE000000`): uninitialized object / corrupted vtable — trace backwards to caller allocation/constructor.
     - Valid code VA missing from `functions.json`: run `scripts/scan_vtables.py` and seed cleanly.
     - Valid function failing mid-body with shifted `esp` / clobbered `edi`: check disassembly for **mid-instruction split** and merge in `recomp_manual.c` (`--exclude-manual`).
2. **Triage `0.00 fps` Freezes & Stalls (Do Not Guess!)**
   - Enable `RECOMP_WATCHDOG_SECS=25`, wait for stall, or attach non-interactively with **`gdb --batch`**:
     ```powershell
     gdb -p <PID> --batch -ex "set pagination off" -ex "thread apply all bt"
     ```
   - Inspect Thread 1 vs NV2A/VBlank threads (details in [freezes-and-deadlocks.md](../troubleshooting/freezes-and-deadlocks.md)):
     - Stuck in `KeWaitForSingleObject` under `RECOMP_PB_WALK=dma` → switch to `RECOMP_PB_WALK=segment`.
     - Stuck spinning on `0xFD100410` → set `RECOMP_FLIP_PACING=0`.
     - Stuck in early `D3D` fence poll → add `xbox_Nv2aMirrorFence(g_pDevice_va, ...)`.
     - Stuck inside `DSOUND` loop on `0xFEC0010B` → bound volatile MMIO re-read in `recomp_manual.c`.
3. **Diagnose Rendering & Shader Glitches (`FTRACE`, Per-RT Dumps, RenderDoc)**
   - Run `RECOMP_PB_SCAN=1` once to rank unimplemented PGRAPH methods used by your game.
   - Dump both the final presented swapchain frame **and** individual offscreen render targets (`s_rts[]`) at a problematic frame to see whether an element failed to render into its offscreen buffer (e.g., missing minimap `clip_x`/`clip_y` scissor, `640×960` AA surface mismatch) or failed during final fullscreen composite (`prim=7` fan, blend mode, bloom RT).
   - Compare draw order, vertex attributes, depth/W-buffer state, combiners, and textures side-by-side against **`xemu`** (OpenGL backend) in **RenderDoc**.
4. **Differential Trace Verification (Logic & Math)**
   - For math/physics/shader divergences, run **RECOMP_VSH_CHECK=1** (vertex shader JIT parity) or compare deterministic trace checkpoints against `xemu` (GDB stub). Fix the **first diverging instruction/function**.

## Rules
- Remove heavy per-draw `[FTRACE]` / BMP dump instrumentation before release profiling (`RECOMP_PB_REPORT_MS=2000` only during bench runs).
- Document every root cause cleanly in `games/<title-id>/notes.md` (and `case-studies/` if reusable).
