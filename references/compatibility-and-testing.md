# Compatibility, Testing & Validation

This reference defines the progressive porting testing pyramid, differential parity checks, scripted UI/gameplay testing, and milestone exit gates.

## 1. Porting Tiers (Scope Control)

Never attempt Tier 3 enhancements before the base game is stable:
- **Tier 0 (Bootable):** Launches cleanly (CLI + Explorer double-click!), initializes kernel/VEH/OHCI/D3D, survives intro FMVs, reaches title screen, stable 10+ minutes.
- **Tier 1 (Vertical Slice):** First playable level/track/stage works with accurate 3D/HUD rendering, depth sorting, minimaps/viewports, playable controls, and audio at `>= 60 FPS`.
- **Tier 2 (Full Game):** Full playthrough, save/load persistence (`TDATA`/`UDATA`), all FMVs, multi-XBE transitions, and input/controller parity.
- **Tier 3 (Enhancements):** Higher internal resolution, widescreen/FOV, uncapped FPS (with delta-time fixes), MSAA/SMAA, HDR.

## 2. Verified Testing Pyramid

1. **Tooling Unit & Script Smoke Tests (Zero Proprietary Data Needed for Core Checks):**
   - Syntax-check and unit-test `scripts/` (`xiso_inspect.py`, `xbe_inspect.py`, `scan_vtables.py`, `probe_containers.py`, `init_port_db.py`, `scaffold_port.py`), kernel path/sync helpers, and `nxdk_pgraph_tests` homebrew images.
2. **CPU & VSH Differential Conformance Tests:**
   - **Vertex Shader JIT Parity (`RECOMP_VSH_CHECK=1`) *[VERIFIED]*:** Execute every NV2A vertex program batch through both the reference field interpreter and the Win64 SSE2 JIT simultaneously, halting/logging on any bitwise float divergence (`>= 10,000,000+` verified runs with `0` mismatches before accepting JIT edits).
   - **Guest CPU Conformance:** Validate lifted x86 instructions (`EFLAGS`, `ADC`/`SBB`, `IMUL`/`IDIV`, x87 precision, SSE `cvtt*`) against Unicorn Engine or `xemu` traces.
3. **Pushbuffer & Kernel Coverage Audits (`RECOMP_PB_SCAN=1`):**
   - Verify unhandled NV2A method counts and unhandled kernel ordinal counters; keep critical init paths free of silent no-ops.
4. **Scripted Gameplay & UI Input Replay (`PAD:` Scripts):**
   - Drive repeatable timed button/trigger scripts (`a`, `start`, `rt`, steering axes) from boot through menus into gameplay, verifying zero crashes/stalls (`> 0.00 fps`), physics/speed response, and repeatable timing across rebuilds.
5. **Visual Per-RT & Golden-Frame Validation:**
   - Capture final swapchain `.bmp` screenshots **plus** intermediate offscreen RT dumps (`s_rts[]`) during complex scenes (SSIM/PSNR or visual diff against `xemu` in RenderDoc). Store commercial captures in gitignored local folders only.
6. **Performance & Standalone Packaging Checks:**
   - Measure `RECOMP_PRESENT_VSYNC=0` + `RECOMP_D3D11_PROF=1` breakdown (`pb`, `rbp`, `vsh`, `srv`, `present`, `cpu(guest/ack)`); remove heavy `[FTRACE]` logs before final benchmarking.
   - Verify launching the release `.exe` directly from Windows Explorer (outside build/dev terminals) loads `default.xbe` cleanly.

## 3. Gate Verification Protocol

Record every completed gate in `reports/gate-log.md`:
- Date, Git commit hash, and exact tool/compiler versions (`MinGW GCC` / `MSVC`, CMake, Python).
- Exact commands executed and observed outputs (post-final-edit results only—explicitly list any skipped tests or open glitches).
- Confirmation that extracted original assets match `reports/disc-manifest.json` SHA-256 hashes and zero copyrighted binaries are tracked in Git.
