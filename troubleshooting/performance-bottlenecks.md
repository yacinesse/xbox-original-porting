# Troubleshooting: Performance Bottlenecks (`15–20 FPS → 60–120+ FPS`)

Never guess why a port is slow—profile both the **guest CPU thread** and the **NV2A pushbuffer/render thread** (`RECOMP_D3D11_PROF=1` + `RECOMP_PB_REPORT_MS=2000`, or `PIX`/`Tracy`).

## Diagnostic Triage Checklist

### 1. Is the CPU Software Rasterizer Still Running?
- **Check:** Unset `RECOMP_PB_EXEC`? Wait—if using a hardware backend, `RECOMP_PB_EXEC=1` MUST be set to parse the pushbuffer, while `s_backend->clear` / `draw` intercepts rendering. However:
  - Setting `RECOMP_PB_EXEC=0` in `xboxrecomp` still enables it because many checks test `getenv(...) != NULL`!
  - Even with `s_backend->clear` registered, check whether `NV097_CLEAR_SURFACE` (`0x1D94`) still calls CPU `zbuf_clear()` (wasting ~5 MB writes per frame). Guard `zbuf_clear()` with `!(s_backend && s_backend->clear)`.

### 2. Are You Hitting MinGW GCC/Clang `__emutls_get_address` TLS Overhead?
- **Symptom:** Profiler shows `libgcc`/`msvcrt`/`__emutls_get_address` consuming 20–40% of guest CPU time.
- **Cause:** On MinGW-w64 Win64, standard `__thread` (`g_eax..g_edi`, `g_xmm0..7`) compiles into function calls on every single register read/write across millions of lifted x86 instructions.
- **Verified Fix:** Enable a single-slot TEB pointer (`RECOMP_FAST_TLS`): allocate one `TlsAlloc()` slot pointing to a flat `RecompThreadState` struct and read `%gs:(teb_offset)` inline via assembly.

### 3. Is `getenv()` or `QueryPerformanceCounter()` Inside a Hot Loop?
- **Symptom:** `ucrtbase!getenv`, `strchr`, or kernel qpc transitions dominate NV2A poll thread CPU profiles.
- **Cause:** Checking `getenv("RECOMP_...")` per draw batch or pushbuffer method (`~20,000+` draws/sec), or calling `QueryPerformanceCounter` inside `xbox_VblankAckHeld()` instead of coarse tick caching.
- **Verified Fix:** Cache every env flag in a `static int` initialized once (`if (v < 0) v = getenv(...) != NULL;`), and replace sub-millisecond vblank/watchdog polls with `GetTickCount()`.

### 4. Is Vertex Shader Microcode Interpreted Instead of JIT-Compiled?
- **Symptom:** `[GPU] rbp=...ms (vsh=...ms)` consumes tens of milliseconds per frame for complex 3D scenes.
- **Verified Fix:**
  1. Enable the Win64 SSE2 VSH JIT (`nv2a_vsh_prepare_jit`) plus a per-batch vertex transform cache (`s_vcache`) and typed `FastAttrStream` fetchers.
  2. **Mandatory Check:** Always validate JIT changes with **`RECOMP_VSH_CHECK=1`** for millions of vertex runs to catch register-aliasing bugs (e.g., `lit` overwriting `out[0]` before reading `c[0]`).

### 5. Is Unbuffered `stderr` or Console Logging Blocking Threads?
- **Symptom:** Rate-limited logs or `[GPU]`/`[KERNEL]` prints stall execution at low FPS.
- **Verified Fix:** Install a large `setvbuf(stderr, buf, _IOFBF, 65536)` in `WinMain` and ensure release builds disable verbose `[PB]`/`[FTRACE]` logging.

### 6. Compiler Optimization & Presentation Flags
- **Compiler (`MinGW`/`Clang`):** Ensure `xbox_kernel` and generated files compile at **`-O3 -fno-math-errno`** (not `-O2`).
- **Swapchain:** Prefer `DXGI_SWAP_EFFECT_FLIP_DISCARD` (`DXGI_PRESENT_ALLOW_TEARING` when `RECOMP_PRESENT_VSYNC=0`) over legacy bitblt `DISCARD`.
- **Host Timer Resolution:** Call `timeBeginPeriod(1)` once at startup so short guest `Sleep(1)` / `KeDelayExecutionThread` yields don't quantize to 15.6 ms windows ticks.
