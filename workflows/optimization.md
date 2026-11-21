# Workflow 8: Performance Profiling & Win64 Optimization

**Goal:** Turn an initially slow (~15–20 FPS) software-heavy bring-up into a responsive **60–120+ FPS** native Windows PC port while maintaining bit-exact shader and simulation correctness.

## Prerequisite Rule
**Never optimize blindly.** Always capture baseline timings first using `RECOMP_D3D11_PROF=1`, `RECOMP_PB_REPORT_MS=2000`, `PIX`, or `Tracy` so every optimization targets a measured bottleneck.

## Optimization Playbook (Highest-ROI Order)

### Step 1: Move Pixel Rasterization Off the CPU
- **Diagnose:** CPU software rasterization + register-combiner blending (`nv2a_pb_exec.c`) typically bottlenecks at `15–20 FPS` (`~50–70 ms/frame`).
- **Fix:** Implement and register a hardware D3D11/D3D12 `Nv2aBackend` with GPU-resident render targets (`s_rts[]`), texture caching, and dynamic combiner HLSL.
- **Gotcha:** Guard `NV097_CLEAR_SURFACE` (`0x1D94`) so it skips the ~5 MB CPU `zbuf_clear()` whenever a hardware `s_backend->clear` is active.

### Step 2: Eliminate MinGW-w64 Emulated TLS Overhead (`RECOMP_FAST_TLS`)
- **Diagnose:** On MinGW GCC/Clang (`_WIN64`), standard `__thread` guest registers (`g_eax..g_edi`, `g_xmm0..7`, `g_fp_stack`) compile to `__emutls_get_address` function calls on nearly every basic block!
- **Fix:** Allocate a single Win32 `TlsAlloc()` slot pointing to a packed `RecompThreadState` struct, resolve its x86-64 `%gs:` TEB slot offset once (`g_recomp_tls_teb_off`), and read it via one inline `movq %gs:(off), reg` instruction.
- **Compiler Flags:** Build `xbox_kernel` and generated files with **`-O3 -fno-math-errno`** (MinGW/Clang) or `/O2` (MSVC).

### Step 3: Accelerate Vertex Programs & Attribute Fetch (with Mandatory Differential Parity)
- **Diagnose:** `[GPU] ... rbp=...ms (vsh=...ms)` dominates pushbuffer thread CPU time when drawing high-poly 3D meshes.
- **Fix:**
  1. Enable the **Win64 SSE2 VSH JIT** (`nv2a_vsh_prepare_jit`) generating native SIMD x64 code for active NV2A vertex programs.
  2. Add a direct per-batch **transformed vertex cache** (`s_vcache`) and inlined typed `FastAttrStream` vertex fetchers bypassing slow bounds-checked helpers per attribute.
  3. Batch pushbuffer array elements (`array_elem16_bulk`, `array_elem32_bulk`), inline vertices, and VSH constant uploads inside `nv2a_pb_scan.c`.
- **MANDATORY VALIDATION GATE:** Run `RECOMP_VSH_CHECK=1` across **millions of vertices** comparing JIT output bitwise against the reference interpreter to catch aliasing bugs (e.g., `lit` overwriting shared `out[0]` before reading `c[0]`)! Zero divergences allowed.

### Step 4: Purge Per-Draw & Per-Tick OS Syscalls
- **Uncached `getenv()`:** Never call `getenv()` inside draw batches, pushbuffer methods, or kernel dispatchers—cache every debug env var once in a `static int`.
- **Per-Tick `QueryPerformanceCounter`:** In busy kernel/vblank polling (`xbox_VblankAckHeld`), replace high-frequency `QPC` syscalls with coarse `GetTickCount()` caching.
- **Unbuffered `stderr`:** Call `setvbuf(stderr, buf, _IOFBF, 65536)` at startup and strip hot diagnostic `[FTRACE]` prints in release builds.
- **Host Timer & Swapchain:** Call `timeBeginPeriod(1)` once so short waits stay responsive, and use **`DXGI_SWAP_EFFECT_FLIP_DISCARD`** (`DXGI_PRESENT_ALLOW_TEARING` when `RECOMP_PRESENT_VSYNC=0`).

### Step 5: Optimize GPU Cache Lookups
- Cache D3D11 blend, depth-stencil, rasterizer, and sampler COM objects by state key (`MAX_BLEND_STATES`, etc.).
- Avoid uploading unchanged constant buffers (`DrawCB`, `CombinerCB`) when identical to last draw.
- Use fast set-associative hashing (`TEX_CACHE_SETS × TEX_CACHE_WAYS`) for guest texture validation, skipping redundant hashes within the same flip unless dynamically mutated (RT/Bink surfaces).

## Exit Gate
- [ ] Differential `RECOMP_VSH_CHECK=1` reports **0** divergences over `>= 10,000,000` vertex runs (if VSH JIT was added/modified).
- [ ] Gameplay reaches `>= 60 FPS` (unlocked benchmark `RECOMP_PRESENT_VSYNC=0`) with balanced guest vs pushbuffer CPU utilization.
- [ ] All timing/FPS improvements are re-measured after cleaning out diagnostic prints.
