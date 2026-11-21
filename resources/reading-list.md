# Technical Reading List & Primary Documentation Index

## 1. Key Deep Dives Inside `sp00nznet/xboxrecomp` (`docs/technical/`)

When cloning `xboxrecomp`, consult these primary engineering documents rather than guessing internals:

| Document | Topic & Key Insight |
|---|---|
| `docs/technical/memory-layout.md` | Why `CreateFileMapping` + 28 mirror views alias 64 MB/contiguous Xbox RAM coherently (`VirtualAlloc` breaks mirror writes) |
| `docs/technical/register-model.md` | Why global TLS registers (`g_eax..g_edi`, `g_esp`) and `void f(void)` functions allow faithful stack/call simulation |
| `docs/technical/indirect-calls.md` | 3-tier `RECOMP_ICALL` dispatch (manual → binary search table → kernel thunk), stack-leak fix (`g_esp += 4`), and ICALL trace ring buffer |
| `docs/technical/pushbuffer-executor.md` | How D3D8LTCG titles kick NV2A pushbuffers, `RECOMP_PB_WALK=segment` vs `dma`, fixed-function lighting, AA surfaces (`2×`), `Nv2aBackend`, and `RECOMP_STRIP_ALT_WINDING` |
| `docs/technical/d3d8ltcg-device-context.md` | Anatomy of XDK D3D8LTCG ~16 KB static device context (`pb_put`, `pb_write_seq`, `pb_gpu_read_ptr` / fence polling) |
| `docs/technical/nv2a-shaders.md` | Register combiners + NV2A vertex program microcode translation & caching |
| `docs/technical/seh-handling.md` | `__SEH_prolog` / `__SEH_epilog` detection and bridging `fs:[0]` |
| `docs/technical/lessons-learned.md` | Critical pitfalls (`DIV0` VEH breaking game SEH, `VirtualAlloc` mirrors, Git Bash CWD bug, rate-limited logs, `.map` backtracing) |
| `docs/technical/candidate-games.md` | Scoring Xbox titles for static recompilation difficulty |
| `docs/technical/ms-fusion-recompiler.md` | Study of Microsoft's Xbox 360 backward-compatibility static recompiler (*Ficl/Fission*) |

## 2. Graphics, Audio & Xbox Format References

- **NV2A Register Combiners & PGRAPH Tests:** `abaire/nxdk_pgraph_tests` and `xemu/hw/xbox/nv2a/` (`vsh.c`, combiner pipeline, swizzling, W-buffering `SET_CONTROL0`).
- **XBE & Kernel Ordinals (`1–378`):** `XboxDev/pyxbe`, `Cxbx-Reloaded/src/common/xbe/Xbe.h`, and `xboxrecomp/docs/formats/` (`xbe.md`, `kernel-exports.md`).
- **XDVDFS Disc Filesystem:** `antangelo/xdvdfs` (verified partition offsets for XISO/XGD1–3).
- **Audio Banks & Codecs:** `vgmstream` XACT `.xwb`/`.xsb` and Xbox IMA ADPCM (36 bytes/64 samples per channel); `FFmpeg` `xmv` and `bink` demuxers.
