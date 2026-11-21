# Troubleshooting Playbook

Diagnose Original Xbox → PC porting failures by **observed symptom** rather than guessing blindly.

## Quick Symptom Index

| Observed Symptom | Most Likely Subsystem | Playbook Guide |
|---|---|---|
| Works in terminal, fails with *"Failed to load default.xbe"* from Windows Explorer | Working directory (`CWD`) lookup | [boot-and-startup.md](boot-and-startup.md) |
| Missing functions or immediate crash calling `D3D`/`DSOUND`/`BINK` sections | Disassembly excluded non-`.text` code sections (`--text-only`) | [boot-and-startup.md](boot-and-startup.md) |
| `0.00 fps` freeze at boot, menu, or mid-FMV while GPU/vblank threads stay alive | D3D8LTCG fence poll, `RECOMP_PB_WALK=dma` `NO_OPERATION` IRQ wait, or MMIO spin-loop (`0xFEC0010B`, `0xFD100410`) | [freezes-and-deadlocks.md](freezes-and-deadlocks.md) |
| Crash or silent skip on indirect call (`RECOMP_ICALL` returns `NULL`), save-screen crash, or `esp` corruption | Unseeded `.rdata` vtable method, corrupted vtable, or **mid-instruction function split** | [icall-and-codegen-bugs.md](icall-and-codegen-bugs.md) |
| Cropped image, wrong viewport/sky depth sorting, missing minimap, inside-out meshes, black Bink textures, or edge vignette | Supersampled AA RT (`2×` height), missing W-buffer shader, missing `clip_x`/`clip_y` scissor, missing `RECOMP_STRIP_ALT_WINDING=1`, or RT-as-SRV hazard | [graphics-and-rendering-glitches.md](graphics-and-rendering-glitches.md) |
| Locked ~15–20 FPS despite fast PC GPU | CPU software rasterizer active, MinGW `__emutls_get_address` TLS overhead, uncached `getenv`/`QPC`, software `zbuf_clear()`, unbuffered `stderr`, or VSH interpreter | [performance-bottlenecks.md](performance-bottlenecks.md) |
| Wrong keyboard driving/action keys (e.g., `'3'` accelerates instead of `'W'`), silent controller, or digital button threshold failure | `RECOMP_KEYBOARD` default bindings, missing `xbox_OhciInit()` / VEH MMIO, or binary `0/1` vs `0..255` analog face button state | [input-and-audio-issues.md](input-and-audio-issues.md) |

## Evidence & Diagnostic Golden Rules

1. **Always check logs before editing code:** Enable rate-limited kernel/GPU/ICALL summaries, then revert heavy logging once diagnosed.
2. **Never blindly suppress exceptions in VEH:** Intercepting `DIV0` or general faults in a Vectored Exception Handler breaks the title's own `__except` handlers (`xboxrecomp` lesson #1).
3. **Treat `getenv("FOO")` carefully:** Many switches in `xboxrecomp` check `!= NULL`, so setting `RECOMP_PB_EXEC=0` still evaluates truthy (**unset** the variable to disable it).
