# Original Xbox → Native PC Porting Skill (`xbox-original-porting`)

A modular, reusable **Google Antigravity Agentic Skill** for analyzing Original Xbox (2001–2005) disc images and executables, selecting between D3D8 HLE and `D3D8LTCG` NV2A pushbuffer static recompilation, building/optimizing native Windows PC ports, and validating behavior against `xemu`.

## Directory Structure

```text
xbox-original-porting/
├── SKILL.md                        # Core agent workflow, mandatory rules & routing matrix
├── README.md                       # Skill layout, setup, and CLI quick start
├── VALIDATION_REPORT.md            # Verification ledger, tested commands & open boundaries
├── workflows/                      # Step-by-step porting procedures (8 files)
│   ├── project-assessment.md       # XISO/XBE triage + HLE vs Pushbuffer decision gate
│   ├── game-analysis.md            # XbSymbolDatabaseCLI, full-section disasm, vtable seeds
│   ├── asset-extraction.md         # Container & entropy forensics
│   ├── code-reconstruction.md      # xboxrecomp C lifting, --exclude-manual, CMake/Ninja
│   ├── implementation.md           # VEH MMIO, OHCI, D3D8LTCG fences, D3D11 backend, input
│   ├── debugging.md                # Crash symbolization, 0.00 fps gdb triage, FTRACE/RenderDoc
│   ├── optimization.md             # RECOMP_FAST_TLS, VSH JIT, syscall/stderr/FLIP_DISCARD
│   └── validation.md               # Differential checks, PAD replay, Explorer standalone test
├── troubleshooting/                # Symptom-driven diagnostic guides (7 files)
│   ├── README.md                   # Symptom routing matrix
│   ├── boot-and-startup.md         # Explorer CWD bug, --text-only traps, VEH vs SEH
│   ├── freezes-and-deadlocks.md    # Fence mirrors, PB_WALK=dma vs segment, APU MMIO loops
│   ├── icall-and-codegen-bugs.md   # Vtable seeds, mid-instruction splits, identified_functions hazard
│   ├── graphics-and-rendering-glitches.md # AA 640x960, W-buffer, clip_x/y scissor, strip winding
│   ├── performance-bottlenecks.md  # CPU rasterizer, __emutls_get_address, uncached getenv/QPC
│   └── input-and-audio-issues.md   # Keymap defaults ('3' throttle), OHCI, 0..255 analog buttons
├── references/                     # Deep technical specifications (10 files)
├── tools/                          # Tool install, rea MCP & CLI guides (5 files)
├── resources/                      # Verified GitHub repos & upstream reading index (2 files)
├── case-studies/juiced/            # Isolated, evidence-graded Juiced (2005) findings (5 files)
├── examples/                       # Reusable configs, CMake, PE TLS header & C templates (8 files)
└── scripts/                        # Python 3.10+ stdlib-only analysis & audit utilities (8 tools)
    ├── xiso_inspect.py             # Read-only XDVDFS (XISO / XGD1-3) inspector & extractor
    ├── xbe_inspect.py              # XBE header, XOR keys, SHA-1, libs & ordinal analyzer
    ├── scan_vtables.py             # Safe .rdata/.data vtable scanner for --seed-functions
    ├── probe_containers.py         # Asset magic, entropy & chunked-zlib archive inspector
    ├── init_port_db.py             # SQLite evidence & function tracking DB initializer
    ├── scaffold_port.py            # Clean, game-data-free workspace generator
    ├── verify_port_release.py      # Standalone PE/DLL/TLS/Explorer/manifest/hygiene auditor
    └── analyze_d3d11_prof.py       # [D3D11-PROF] FPS tier summarizer & bottleneck detector
```

## Installation in Google Antigravity

### Workspace Scope (Recommended for Porting Repositories)
```powershell
Copy-Item -Recurse "xbox-original-porting" "<your-project>\.agent\skills\xbox-original-porting"
```

### Global User Scope
```powershell
Copy-Item -Recurse "xbox-original-porting" "$env:USERPROFILE\.gemini\config\skills\xbox-original-porting"
```

## Requirements

- **Python 3.10+** — all 8 utilities in `scripts/` use the **Python standard library only** (`capstone` is needed separately when running `xboxrecomp` disassembly/lifting).
- External tools per porting project (see [tools/xboxrecomp-guide.md](tools/xboxrecomp-guide.md) & [resources/repositories.md](resources/repositories.md)):
  - CMake `>= 3.20`, Ninja, MSVC (VS 2022) or WinLibs MinGW-w64 GCC + GDB
  - `sp00nznet/xboxrecomp`, `Cxbx-Reloaded/XbSymbolDatabase`, `xemu`, RenderDoc, Ghidra + `XboxDev/ghidra-xbe`, FFmpeg / `vgmstream`

## Quick Usage (Stdlib Python Tools)

```powershell
# 1. Inspect & extract an XISO/Redump XGD1 image read-only
py -3 scripts/xiso_inspect.py path\to\game.iso --extract private\extracted\GAME --manifest reports\disc-manifest.json

# 2. Decode default.xbe (headers, 35+ sections, D3D8 vs D3D8LTCG, kernel ordinals)
py -3 scripts/xbe_inspect.py private\extracted\GAME\default.xbe --json reports\xbe-info.json

# 3. Scan .rdata/.data vtables safely into seed_functions.json (blocking interior splits)
py -3 scripts/scan_vtables.py private\extracted\GAME\default.xbe --functions Research\disasm\functions.json --strict-prologue -o Research\seed_vtables.json

# 4. Probe custom .dat/.bin/.zbg containers (entropy, zlib chunks, embedded signatures)
py -3 scripts/probe_containers.py private\extracted\GAME --recursive --decompress-preview --json reports\asset-probe.json

# 5. Scaffold a clean port project & initialize reports/port.db
py -3 scripts/scaffold_port.py my-xbox-port --title-id 545100EF --name "My Xbox Game"
py -3 scripts/init_port_db.py my-xbox-port\reports\port.db --from-xbe-json reports\xbe-info.json

# 6. Profile [D3D11-PROF] logs & audit final standalone release (PE/DLLs/TLS/Explorer/manifest)
py -3 scripts/analyze_d3d11_prof.py private\logs\opt_bench.log --markdown
py -3 scripts/verify_port_release.py build\recomp\game_port.exe --obj-dir build\recomp\CMakeFiles --test-explorer 12 --manifest reports\disc-manifest.json --extracted private\extracted\disc --repo .
```

## Keeping the Skill Game-Agnostic

- Place general Xbox knowledge inside `workflows/`, `references/`, `troubleshooting/`, `tools/`, `examples/`, and `scripts/`.
- Isolate title-specific addresses, bugs, and open issues under `case-studies/<title>/` (for example, [case-studies/juiced/](case-studies/juiced/README.md)) so other ports never inherit title-specific assumptions blindly.
