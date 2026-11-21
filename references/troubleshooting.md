# Troubleshooting Hub (Moved to `troubleshooting/`)

Detailed symptom-first troubleshooting playbooks have been expanded into the dedicated **[troubleshooting/](../troubleshooting/README.md)** directory based on real bring-up, freeze, codegen, graphics, performance, and input failures:

- **[Symptom Index & Triage Rules](../troubleshooting/README.md)**
- **[Boot, Explorer CWD & XBE/XISO Errors](../troubleshooting/boot-and-startup.md)**
- **[Freezes, Deadlocks & `0.00 fps` Stalls](../troubleshooting/freezes-and-deadlocks.md)** (`D3D8LTCG` fence mirrors, `RECOMP_PB_WALK=dma` vs `segment`, `0xFEC0010B` APU loops, `0xFD100410` flip-holds, `KeStallExecutionProcessor` DSP waits)
- **[ICALL Failures, `.rdata` Vtables & Mid-Instruction Splits](../troubleshooting/icall-and-codegen-bugs.md)** (`recomp_manual.c`, `--exclude-manual`, `identified_functions.json` seed hazard)
- **[Graphics, W-Buffer, AA Surfaces, Minimaps & Shaders](../troubleshooting/graphics-and-rendering-glitches.md)** (`640×960` cropping, `control0 & 0x10000`, `clip_x`/`clip_y` scissor rects, `RECOMP_STRIP_ALT_WINDING`, Bink YUY2 refresh, unresolved radial vignette fan notes)
- **[Performance Bottlenecks (`15–20 FPS → 90–120+ FPS`)](../troubleshooting/performance-bottlenecks.md)** (`RECOMP_FAST_TLS`, SSE2 VSH JIT + `RECOMP_VSH_CHECK`, `zbuf_clear()` skip, uncached `getenv`/`QPC`, `FLIP_DISCARD`)
- **[Input, Controller & Audio Issues](../troubleshooting/input-and-audio-issues.md)** (`'3'` vs `'W'` keymap defaults, `xbox_OhciInit`, analog `0..255` face buttons, AC97 readiness)
