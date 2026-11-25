---
name: xbox-original-porting
description: Structured, evidence-driven workflow, troubleshooting playbooks, stdlib Python inspection/audit/profiling tools, Win64 PE TLS & D3D11 NV2A templates, and runtime architecture reference for porting Original Xbox (2001–2005) games to standalone native Windows PC executables. Use when inspecting XISO/XGD1 disc images, analyzing XBE headers or D3D8LTCG binaries, running xboxrecomp and XbSymbolDatabase pipelines, recovering C++ vtables, implementing hardware NV2A D3D11 pushbuffer backends (W-buffer, RT self-sampling snapshots, Fibonacci texture caches), debugging driver crashes or freezes, optimizing Win64 PE TLS and SSE2 VSH JIT, or auditing zero-DLL Explorer releases.
---

# Original Xbox → Native PC Porting Skill

Guide every Original Xbox (2001–2005) porting project through a systematic, evidence-driven pipeline from read-only disc inspection to a verified native Windows executable. Evaluate every title from its actual `default.xbe` and extracted assets rather than assuming engine or XDK behavior.

## Mandatory Operating Rules

1. **Evidence & Honest Status Tagging:** Never guess function signatures, struct offsets, kernel ordinals, or file formats. Track claims in `reports/port.db` with `source`, `method`, and `confidence`, and label port findings as **`VERIFIED`**, **`EXPERIMENTAL`**, **`THEORETICAL`**, or **`UNRESOLVED`**.
2. **AI-Assisted RE Confidence Cap:** Proposals from AI/MCP tools (`REA`, `ReVa`, `ghidra-mcp`) remain capped at `medium` confidence until confirmed by disassembly xrefs, dynamic traces (`xemu` / `gdb`), or differential checks (`RECOMP_VSH_CHECK=1`).
3. **No Silent No-Ops:** Unimplemented kernel ordinals, NV2A methods, or hardware waits must log (rate-limited) and count failures rather than silently corrupting state.
4. **Source Immutability & Legal Hygiene:** Never modify original disc dumps or extracted files (`scripts/xiso_inspect.py` sets `0444`). Never commit `.iso`, `.xbe`, `.xpr`, `.xwb`, `.xmv`, `.bik`, game screenshots, or generated commercial C/C++ files to Git (`scripts/scaffold_port.py` configures `.gitignore`). Keep your port repo separate from upstream external toolkits.
5. **Untrusted Input & Safe VEH Rules:** Treat binaries, strings, and archive headers as untrusted data. Never intercept general CPU exceptions (`DIV0`, game SEH) in a Windows VEH—delegate strictly hardware MMIO ranges (`xbox_VehMmioFault`).
6. **Incremental Tier Gating:** Do not attempt Tier 3 enhancements before Tier 2 passes cleanly:
   - **Tier 0:** Boots natively (CLI + Windows Explorer!), survives FMVs, reaches title screen, 10+ min stability.
   - **Tier 1:** Playable vertical slice with accurate uncropped rendering, depth sorting, HUD/minimaps, audio, and playable controls at `>= 60 FPS`.
   - **Tier 2:** Full game playthrough, `TDATA`/`UDATA` save persistence, FMVs, multi-XBE switching.
   - **Tier 3:** Resolution scaling, widescreen/FOV, uncapped FPS (with delta-time scaling), MSAA/SMAA.

## Quick Strategy Decision Gate (Choose Before Writing Runtime Code)

1. Extract `default.xbe` and run `scripts/xbe_inspect.py` + `XbSymbolDatabaseCLI.exe`:
   - **`D3D8LTCG` present OR `< 90%` D3D8 API match OR custom pushbuffers *[VERIFIED Path]*:**
     Use **`sp00nznet/xboxrecomp`** static recompilation across **ALL code sections** (omit `--text-only`) + NV2A pushbuffer execution (`RECOMP_PB_EXEC=1`, `RECOMP_PB_WALK=segment`) + hardware **Direct3D 11 `Nv2aBackend`** (`nv2a_backend.h`). Do *not* rely on the CPU software rasterizer (`~15 FPS`) or partial API HLE.
   - **Standard `D3D8` (`>= 90%` XDK symbol match):**
     Choose **`XboxXBERecomp`** (`D3D12` HLE) or `xboxrecomp` (`xbox_d3d8` D3D11 HLE).
   - **Clean-Room C++/D3D12 Rewrite (`Anti-Pattern Warning`):**
     Avoid clean-room engine reimplementation when authentic menus, UI state machines, shaders, and physics are required unless official game source code exists. Static recompilation retains 100% original behavior.

## End-to-End Porting Workflow

Execute sequentially, passing each workflow's Exit Gate before advancing:

| Stage | Activity | Playbook & Tooling |
|---|---|---|
| **1. Assessment & Strategy** | Read-only XISO/XGD1 extraction, XBE analysis, strategy ADR, workspace scaffold, `port.db` init | [project-assessment.md](workflows/project-assessment.md), `scripts/xiso_inspect.py`, `scripts/xbe_inspect.py`, `scripts/scaffold_port.py` |
| **2. Deep Binary Analysis** | `XbSymbolDatabaseCLI`, RTTI/PDB strings, full-section `tools.disasm`, safe `.rdata` vtable seeding | [game-analysis.md](workflows/game-analysis.md), `scripts/scan_vtables.py`, [xbsymboldatabase-guide.md](tools/xbsymboldatabase-guide.md) |
| **3. Asset & Archive Forensics** | Signature + entropy scan, `.dat` chunked-zlib / `.zbg` / `.xbx` probing, bounds-checked readers | [asset-extraction.md](workflows/asset-extraction.md), `scripts/probe_containers.py` |
| **4. Code Reconstruction** | `xboxrecomp` (`xbe_parser -> disasm -> func_id -> abi_analysis -> recomp`), `--exclude-manual`, Ninja `-O3` build | [code-reconstruction.md](workflows/code-reconstruction.md), [xboxrecomp-guide.md](tools/xboxrecomp-guide.md) |
| **5. Runtime Bring-Up** | Explorer CWD & `-static -static-libgcc`, VEH MMIO, `xbox_OhciInit()`, `D3D_g_pDevice` fence mirror, D3D11 NV2A backend (active RT extent, RT self-sampling snapshots, SRV pinning), genre input | [implementation.md](workflows/implementation.md), [recomp_main_template.c](examples/recomp_main_template.c), [CMakeLists.port.example](examples/CMakeLists.port.example) |
| **6. Debugging & Triage** | Watchdog + `gdb --batch` / `SymFromAddr` backtraces, MMIO & `-O3` KEVENT fixes, `ICALL` / mid-split fixes, `nvwgf2umx.dll` SRV hazards, `FTRACE` + RenderDoc | [debugging.md](workflows/debugging.md), [troubleshooting/README.md](troubleshooting/README.md) |
| **7. Win64 Optimization** | `RECOMP_FAST_TLS` (`%gs:` PE `.CRT$XLB`), SSE2 VSH JIT (`RECOMP_VSH_CHECK=1`) + `FastAttrStream`, Fibonacci texture cache hash (`miss=0`), dirty cubemaps, `zbuf_clear` bypass | [optimization.md](workflows/optimization.md), [recomp_fast_tls.h](examples/recomp_fast_tls.h), `scripts/analyze_d3d11_prof.py`, [performance-bottlenecks.md](troubleshooting/performance-bottlenecks.md) |
| **8. Validation & Gates** | Differential checks (`RECOMP_VSH_CHECK`), `PAD:` replay, zero-DLL PE/TLS/Explorer audit, manifest SHA-256 & hygiene check, `gate-log.md` | [validation.md](workflows/validation.md), `scripts/verify_port_release.py`, [compatibility-and-testing.md](references/compatibility-and-testing.md) |

## On-Demand Knowledge Index

- **Symptom Troubleshooting (Start Here When Stuck):** [troubleshooting/README.md](troubleshooting/README.md) — [Boot/CWD/DLLs](troubleshooting/boot-and-startup.md) | [Freezes/`0.00 fps`](troubleshooting/freezes-and-deadlocks.md) | [ICALL/Splits](troubleshooting/icall-and-codegen-bugs.md) | [Graphics/W-Buffer/Vignette/Crashes](troubleshooting/graphics-and-rendering-glitches.md) | [Performance/TLS/Cache Hash](troubleshooting/performance-bottlenecks.md) | [Input/Audio](troubleshooting/input-and-audio-issues.md)
- **Technical Deep Dives:** [Architecture/MMIO/TLS](references/xbox-architecture.md) | [XBE/XGD1](references/executable-analysis.md) | [RE/Vtables/Splits](references/reverse-engineering.md) | [Assets/Containers](references/asset-extraction.md) | [D3D8/NV2A/D3D11](references/graphics-and-rendering.md) | [Audio/FMV/Input](references/audio-and-input.md) | [Runtime Integration](references/game-engine-integration.md)
- **Tool Guides & Templates:** [xboxrecomp](tools/xboxrecomp-guide.md) | [XbSymbolDatabase](tools/xbsymboldatabase-guide.md) | [Python Scripts](tools/custom-analysis-tools.md) | [Advanced RE (`rea` MCP) & Release Tools](tools/rea-and-advanced-tools.md) | [Debugging/Profiling](tools/debugging-and-profiling-tools.md) | [Fast TLS Header](examples/recomp_fast_tls.h) | [CMake Template](examples/CMakeLists.port.example)
- **Reference Case Study & Repos:** [*Juiced* (2005) Case Study](case-studies/juiced/README.md) | [Verified Repos](resources/repositories.md) | [Reading List](resources/reading-list.md)
