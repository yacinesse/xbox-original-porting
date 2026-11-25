# Troubleshooting: Performance Bottlenecks (`15–20 FPS → 70–128+ FPS`)

Never guess why a port is slow—profile both the **guest CPU thread** and the **NV2A pushbuffer/render thread** (`RECOMP_D3D11_PROF=1` + `RECOMP_PB_REPORT_MS=2000`, parsed via `scripts/analyze_d3d11_prof.py`, or `PIX`/`Tracy`).

## Diagnostic Triage Checklist

### 1. Is the CPU Software Rasterizer Still Running?
- **Check:** For a hardware backend, `RECOMP_PB_EXEC=1` MUST be set to parse the pushbuffer, while `s_backend->clear` / `draw` intercepts rendering. However:
  - Setting `RECOMP_PB_EXEC=0` in `xboxrecomp` still enables it because presence checks test `getenv(...) != NULL`!
  - Even with `s_backend->clear` registered, check whether `NV097_CLEAR_SURFACE` (`0x1D94`) still calls CPU `zbuf_clear()` (wasting ~5 MB writes per frame). Guard `zbuf_clear()` with `!(s_backend && s_backend->clear)`.

### 2. Are You Hitting MinGW GCC/Clang `__emutls_get_address` TLS Overhead?
- **Symptom:** Profiler shows `libgcc` / `__emutls_get_address` consuming 20–40% of guest CPU time, or `scripts/verify_port_release.py --obj-dir ...` reports `__emutls_get_address` hits.
- **Cause:** On MinGW-w64 Win64, standard `__thread` (`g_eax..g_edi`, `g_xmm0..7`) compiles into function calls on every single register read/write across millions of lifted x86 instructions.
- **Verified Fix (`examples/recomp_fast_tls.h`):**
  1. Allocate one Win32 `TlsAlloc()` slot (`< 64`) in a PE64 `.CRT$XLB` `PIMAGE_TLS_CALLBACK` so every host thread gets an aligned `RecompFastTlsState` at `gs:[0x1480 + slot * 8]` read via `__attribute__((always_inline, const))`.
  2. **Pitfall 1 (Macro Expansion):** Prefix struct members with `r_` (`r_eax`, `r_esp`, ...) because `recomp_types.h` defines `#define eax g_eax`!
  3. **Pitfall 2 (Linker Strip):** Anchor `extern const IMAGE_TLS_DIRECTORY _tls_used;` inside `recomp_fast_tls_verify_init()` so MinGW `-static` keeps PE DataDirectory[9] (`.tls`).
  4. **Pitfall 3 (Local Static TLS):** Keep local TLS macros (`APU_TLS`, `OHCI_TLS`) **outside** `#ifndef RECOMP_FAST_TLS_ACTIVE`.
  5. Verify with `scripts/verify_port_release.py` (`PE .tls PRESENT`, `0` `__emutls_get_address` hits) and runtime `[FAST-TLS] Win64 TEB slot ... verified`.

### 3. Is Vertex Shader Microcode Interpreted Instead of JIT-Compiled?
- **Symptom:** `[GPU] rbp=...ms (vsh=...ms)` dominates pushbuffer thread CPU time on high-poly 3D meshes (`100k–160k` verts/frame).
- **Verified Fix:**
  1. Implement/enable the **Win64 x86-64 SSE2 VSH JIT** (`nv2a_vsh_prepare_jit` in a `VirtualAlloc` RWX arena with a 128-entry hash cache), plus per-batch vertex transform cache (`s_vcache`) and **`FastAttrStream` + `nv2a_vsh_input_mask()`** (compute active input bitmask during `dec_program()` so `raster_batch_program()` skips fetching unused vertex attributes!).
  2. **Exact IEEE-754 Pitfalls to Watch:**
     - Match scalar `vsh_run_fields` addition order in `DP3`/`DPH`/`DP4` and exact `-0.0f`/`NaN` parity for `MIN`/`MAX`/`RCC`/`RCP` + `vsh_finish` clamp.
     - Route `ARL`/`EXP`/`LOG`/`LIT` through non-aliasing C helpers (prevents `lit` overwriting `out[0]` before reading `c[0]`).
     - Never name local C helper functions `j1` in files including `<math.h>` (POSIX/MinGW declares Bessel function `double j1(double)` — use `jb1`/`jb4`).
  3. **Mandatory Gate:** Run **`RECOMP_VSH_CHECK=1`** for `>= 10,000,000` vertex executions (verified at `67,108,864` runs, `0` divergences) across menus + 3D gameplay!

### 4. Are Texture Cache Hash Collisions Burning `3–5 ms/frame`? (>30× Speedup!)
- **Symptom:** `[D3D11-PROF]` shows steady-state `miss=100..250` and `tex=3.0–5.0 ms` in 3D scenes even after warming up (automatically flagged by `scripts/analyze_d3d11_prof.py`).
- **Root Cause:** Xbox DXT5/swizzled textures are commonly 2048-byte aligned; naive shift/XOR hashes collapse all aligned addresses onto a tiny subset of sets (e.g., `17 mod 32` — only 16 of 512 sets!), thrashing the cache every frame! Unused `palette` or `pitch` fields on non-palettized/normalized textures also cause spurious key mismatches.
- **Verified Fix:**
  1. Gate texture stage lookups by active `rs->rc.stage_program` (`modes 1..3` only).
  2. Canonicalize key fields: `eff_pal = (color == 0x0B) ? palette : 0`, `eff_pitch = norm ? 0 : pitch`.
  3. Use a **multiplicative Fibonacci hash** mixing bits `6..31` over a `512 × 8` cache:
     `((offset >> 6 ^ offset >> 11 ^ offset >> 17 ^ color * 0x9E3779B1u ^ width * 131u ^ eff_pal >> 5) * 0x9E3779B1u) >> 23`.
  4. **Measured Impact:** Drops steady-state misses from `~180/frame` to **`0`**, cutting `tex` from `3.5–4.7 ms` to **`0.12–0.15 ms`**!

### 5. Are Dynamic Cubemap Face Syncs Copying Unchanged Faces Every Draw?
- **Symptom:** `[D3D11-PROF]` reports `cube=100..200+` copies per frame on reflective vehicles/objects.
- **Verified Fix:** Track `write_seq` per `GpuRT` and `cube_face_seq[6]` per cached cubemap; only issue `CopySubresourceRegion` when a face RT's `write_seq` changed since last sync (`193 → 3` copies/frame).

### 6. Are `getenv()`, `QueryPerformanceCounter()`, or Hot `stderr` Logs Blocking Threads?
- **Uncached `getenv()`:** Cache every debug env flag once in a `static int` (`if (v < 0) v = getenv(...) != NULL;`).
- **Hot-Path `stderr` Spam:** Gate per-read `[READ]` logs (`kernel_bridge.c`) behind `RECOMP_LOG_READ` and per-draw `[GPU] draw #` logs (`nv2a_pb_exec.c`) behind `RECOMP_PB_EXEC_VERBOSE`. Install `setvbuf(stderr, buf, _IOFBF, 65536)` at startup.
- **Per-Tick `QPC`:** Replace tight `QueryPerformanceCounter` calls in vblank polls (`xbox_VblankAckHeld`) with coarse `GetTickCount()` caching.

### 7. Compiler Optimization & Presentation Flags
- **Compiler (`MinGW`/`Clang`):** Build `xbox_kernel` and generated files at **`-O3 -fno-math-errno`** (not `-O2`).
- **Swapchain:** Prefer `DXGI_SWAP_EFFECT_FLIP_DISCARD` (`DXGI_PRESENT_ALLOW_TEARING` when `RECOMP_PRESENT_VSYNC=0`) over legacy bitblt `DISCARD`.
- **Host Timer Resolution:** Call `timeBeginPeriod(1)` once at startup so short `Sleep(1)` / `KeDelayExecutionThread` yields don't quantize to 15.6 ms Windows ticks.
