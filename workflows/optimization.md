# Workflow 8: Performance Profiling & Win64 Optimization

**Goal:** Turn an initially slow (~15–20 FPS) software-heavy bring-up into a responsive **60–120+ FPS** native Windows PC port while maintaining bit-exact shader and simulation correctness.

## Prerequisite Rule
**Never optimize blindly.** Always capture baseline timings first using `RECOMP_D3D11_PROF=1` + `RECOMP_PB_REPORT_MS=2000` (and analyze via `py -3 scripts/analyze_d3d11_prof.py <log> --markdown`), `PIX`, or `Tracy` so every optimization targets a measured bottleneck.

## Optimization Playbook (Highest-ROI Order)

### Step 1: Move Pixel Rasterization Off the CPU
- **Diagnose:** CPU software rasterization + register-combiner blending (`nv2a_pb_exec.c`) typically bottlenecks at `15–20 FPS` (`~50–70 ms/frame`).
- **Fix:** Implement and register a hardware D3D11/D3D12 `Nv2aBackend` with GPU-resident render targets (`s_rts[]`), texture caching, and dynamic combiner HLSL.
- **Gotcha:** Guard `NV097_CLEAR_SURFACE` (`0x1D94`) so it skips the ~5 MB CPU `zbuf_clear()` whenever a hardware `s_backend->clear` is active.

### Step 2: Eliminate MinGW-w64 Emulated TLS Overhead (`RECOMP_FAST_TLS`)
- **Diagnose:** On MinGW GCC/Clang (`_WIN64`), standard `__thread` guest registers (`g_eax..g_edi`, `g_xmm0..7`, `g_fp_stack`) compile to `__emutls_get_address` function calls on nearly every basic block! Audit with `py -3 scripts/verify_port_release.py <exe> --obj-dir <build_dir>`.
- **Fix:** Implement [examples/recomp_fast_tls.h](../examples/recomp_fast_tls.h): register a PE64 `.CRT$XLB` `PIMAGE_TLS_CALLBACK` allocating one Win32 `TlsAlloc()` slot (`< 64`) pointing to an aligned `RecompFastTlsState` (`r_`-prefixed members to avoid `#define eax g_eax` macro expansion!), anchor `_tls_used` so static linking keeps DataDirectory[9], read `%gs:(g_recomp_teb_off)` via `__attribute__((always_inline, const))`, and call `recomp_fast_tls_verify_init()` at startup.
- **Compiler Flags:** Build `xbox_kernel` and generated files with **`-O3 -fno-math-errno -DRECOMP_FAST_TLS=1`** (MinGW/Clang) or `/O2` (MSVC).

### Step 3: Accelerate Vertex Programs & Attribute Fetch (with Mandatory Differential Parity)
- **Diagnose:** `[GPU] ... rbp=...ms (vsh=...ms)` dominates pushbuffer thread CPU time when drawing high-poly 3D meshes (`100k–160k` verts/frame).
- **Fix:**
  1. Enable the **Win64 SSE2 VSH JIT** (`nv2a_vsh_prepare_jit` in a `VirtualAlloc` RWX arena with 128-entry hash cache), preserving exact `DP3`/`DPH`/`DP4` addition order and `-0.0f`/`NaN` parity for `MIN`/`MAX`/`RCC`/`RCP`, and using non-aliasing C helpers for `ARL`/`EXP`/`LOG`/`LIT`.
  2. Compute `nv2a_vsh_input_mask()` during `dec_program()` and combine with a per-batch **transformed vertex cache** (`s_vcache`) + typed **`FastAttrStream`** fetchers so `raster_batch_program()` skips fetching unused vertex attributes!
  3. Batch pushbuffer array elements (`array_elem16_bulk`, `array_elem32_bulk`), inline vertices, and VSH constant uploads inside `nv2a_pb_scan.c`.
- **MANDATORY VALIDATION GATE:** Run `RECOMP_VSH_CHECK=1` across **`>= 10,000,000` vertices** comparing JIT output bitwise against the reference interpreter to catch aliasing or signed-zero bugs! Zero divergences allowed.

### Step 4: Purge Per-Draw & Per-Tick OS Syscalls and Hot Logs
- **Uncached `getenv()`:** Never call `getenv()` inside draw batches, pushbuffer methods, or kernel dispatchers—cache every debug env var once in a `static int`.
- **Per-Tick `QueryPerformanceCounter`:** In busy kernel/vblank polling (`xbox_VblankAckHeld`), replace high-frequency `QPC` syscalls with coarse `GetTickCount()` caching.
- **Unbuffered `stderr` & Hot Logs:** Call `setvbuf(stderr, buf, _IOFBF, 65536)` at startup, gate `[READ]` logs behind `RECOMP_LOG_READ` and `[GPU] draw #` behind `RECOMP_PB_EXEC_VERBOSE`, and strip `[FTRACE]` prints in release builds.
- **Host Timer & Swapchain:** Call `timeBeginPeriod(1)` once so short waits stay responsive, and use **`DXGI_SWAP_EFFECT_FLIP_DISCARD`** (`DXGI_PRESENT_ALLOW_TEARING` when `RECOMP_PRESENT_VSYNC=0`).

### Step 5: Optimize GPU Cache Lookups & Eliminate Hash Collisions
- Cache D3D11 blend, depth-stencil, rasterizer, and sampler COM objects by state key (`MAX_BLEND/DEPTH/SAMPLERS = 256`).
- Avoid uploading unchanged constant buffers (`DrawCB`, `CombinerCB`) when identical to last draw.
- Use a **`512 × 8`** texture cache with **multiplicative Fibonacci hashing** (`offset >> 6 ^ offset >> 11 ^ offset >> 17 ... * 0x9E3779B1u`) to avoid 2048-byte aligned DXT5 set collisions (`miss=180 → 0`, `tex: 3.5–4.7ms → 0.12–0.15ms`), gate lookups by `rs->rc.stage_program` (`modes 1..3`), canonicalize unused `palette`/`pitch` keys, and dirty-track dynamic cubemap face RT syncs via `write_seq` (`cube: 193 → 3`).

## Exit Gate
- [ ] Differential `RECOMP_VSH_CHECK=1` reports **0** divergences over `>= 10,000,000` vertex runs (if VSH JIT was added/modified).
- [ ] Gameplay reaches `>= 60 FPS` (unlocked benchmark `RECOMP_PRESENT_VSYNC=0`) with balanced guest vs pushbuffer CPU utilization.
- [ ] All timing/FPS improvements are re-measured after cleaning out diagnostic prints.
