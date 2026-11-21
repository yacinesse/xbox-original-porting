# Workflow 1: Project Assessment & Strategy Selection

**Goal:** Inspect the user-supplied disc dump or game directory, analyze `default.xbe`, evaluate technical feasibility using an explicit strategy rubric, and scaffold a clean, game-data-free porting workspace.

## Prerequisites
- User supplies their own legal disc dump (`.iso`/`.xiso`) or extracted game directory.
- Never modify original game files.

## Steps

1. **Inspect Disc Image (Read-Only)**
   - Run `scripts/xiso_inspect.py` to detect XISO or Redump XGD1 (`0x18300000`) / XGD2 / XGD3 partition offsets, list all files, and locate `default.xbe` plus any secondary `.xbe` executables:
     ```powershell
     py -3 scripts/xiso_inspect.py <path/to/game.iso> --no-hash
     ```
2. **Extract `default.xbe` (or Full Disc) to `private/`**
   - Extract safely with read-only permissions (`0444`) and SHA-256 manifest:
     ```powershell
     py -3 scripts/xiso_inspect.py <path/to/game.iso> --extract private/extracted/<title-id> --manifest reports/disc-manifest.json
     ```
3. **Inspect XBE Metadata & Sections**
   - Run `scripts/xbe_inspect.py` on `default.xbe` (and secondary `.xbe`s):
     ```powershell
     py -3 scripts/xbe_inspect.py private/extracted/<title-id>/default.xbe --json reports/xbe-info.json
     ```
   - Record: `TitleID`, `Build Type` (`Retail` / `Debug` / `Chihiro`), **all section names & executable flags** (`D3D`, `D3DX`, `DSOUND`, `XACTENG`, `XPP`, `BINK*`, `WMADEC`, `DOLBY`), `libraries` (`D3D8` vs `D3D8LTCG`, XDK build number), and `kernel_imports` count.
4. **Scaffold Workspace & Initialize Evidence DB**
   - Run `scripts/scaffold_port.py` and `scripts/init_port_db.py`:
     ```powershell
     py -3 scripts/scaffold_port.py <project-dir> --title-id <TITLE_ID> --name "<Game Name>"
     py -3 scripts/init_port_db.py <project-dir>/reports/port.db --from-xbe-json reports/xbe-info.json
     ```
   - Keep the game port repository completely separate from external toolkits (`Tools/external/xboxrecomp`, `Tools/external/XbSymbolDatabase`).
5. **Apply Architecture Decision Matrix (Choose Porting Strategy)**
   - Evaluate using [port-assessment-template.md](../examples/port-assessment-template.md) and record the choice in `docs/adr/` ([adr-template.md](../examples/adr-template.md)):

| Observed Signal in `default.xbe` | Recommended Strategy | Why |
|---|---|---|
| **`D3D8LTCG` detected** OR `< 90%` D3D8 symbol match OR heavy custom NV2A shaders | **`xboxrecomp` + Pushbuffer Execution (`RECOMP_PB_EXEC=1`) + Hardware D3D11 `Nv2aBackend`** *[VERIFIED]* | LTCG inlines D3D helpers and uses register calling conventions that break API-level HLE hooks; executing the NV2A pushbuffer directly preserves authentic graphics |
| **Standard `D3D8` (`>= 90%` XbSymbolDatabase/FID match)** + C++/D3D12 target | **`XboxXBERecomp` (D3D8 HLE) or `xboxrecomp` (`xbox_d3d8`)** *[THEORETICAL / UPSTREAM DOCS]* | Clean API boundary allows intercepting `IDirect3DDevice8` directly into D3D12 or D3D11 |
| **Open-source engine / complete PC source equivalent** OR goal is purely asset viewer | **Custom / Clean-Room Engine** *(Caution!)* | Attempting clean-room reimplementation for full commercial Xbox gameplay, menus, UI state machines, and physics typically fails to match authentic UI/behavior without months of clean-room RE |

## Exit Gate (Gate 0 / Assessment Complete)
- [ ] `reports/disc-manifest.json` and `reports/xbe-info.json` generated without modifying source files.
- [ ] `reports/port.db` initialized with all kernel imports.
- [ ] Feasibility assessment, porting strategy (`xboxrecomp` pushbuffer vs D3D8 HLE), and Tier 0–3 scope approved.
