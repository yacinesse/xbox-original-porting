# Workflow 2: Deep Game & Binary Analysis

**Goal:** Recover XDK symbols, fingerprint middleware, map all code sections, and build a verified function/vtable seed list before code lifting.

## Steps

1. **Run Fast CLI Symbol Recovery (`XbSymbolDatabaseCLI`)**
   - Before slow manual RE, run `XbSymbolDatabaseCLI.exe` (see [xbsymboldatabase-guide.md](../tools/xbsymboldatabase-guide.md)) against `default.xbe`:
     ```powershell
     .\Builds\xbsym\projects\cli\XbSymbolDatabaseCLI.exe private/extracted/<TITLE_ID>/default.xbe > Research/xbe_symbols.txt
     ```
   - Immediately note critical XDK globals such as `D3D8LTCG__D3D_g_pDevice` (needed for fence mirroring) and `DSOUND__CMcpxAPU_*` addresses.
2. **Fingerprint Engine, Middleware & Multi-XBEs**
   - Scan `.rdata`/`.data` strings for MSVC RTTI class names (`.?AV*@@` / `.?AU*@@`), PDB paths (e.g., `*\Release\*.pdb`), source file paths, and engine anchors (RenderWare, Havok, Unreal, Gamebryo, Bink, XACT, Redline/custom).
   - Check for multi-XBE transitions (`XLaunchNewImage` calls or `.xbe` filenames in strings).
   - Optionally inspect with `Detect It Easy` (`diec`) or `capa` inside a sandboxed folder.
3. **Run Full-Section Static Disassembly (Beyond `.text`)**
   - Parse the XBE with `xboxrecomp` (`tools.xbe_parser ... --json <xbe_stem>_analysis.json`).
   - Check `reports/xbe-info.json` for statically linked XDK/middleware sections (`D3D`, `D3DX`, `DSOUND`, `XACTENG`, `XPP`, `XONLINE`, `XNET`, `BINK*`, `WMADEC`, `DOLBY`).
   - Run `tools.disasm` across **all code sections** (do NOT pass `--text-only` if XDK/middleware code lives outside `.text`; pass `--extra-sections ...` for any unflagged code section).
4. **Recover `.rdata`/`.data` Vtables Safely**
   - Static recursive descent routinely misses virtual methods called only via C++ vtables (`ICALL`).
   - Run `scripts/scan_vtables.py` filtered against `disasm/functions.json` (and optionally `--strict-prologue`):
     ```powershell
     py -3 scripts/scan_vtables.py private/extracted/<TITLE_ID>/default.xbe `
         --functions Research/disasm/functions.json `
         --strict-prologue `
         -o Research/seed_functions_vtables.json
     ```
   - Re-run `tools.disasm` with `--seed-functions Research/seed_functions_vtables.json`.
   - **Rule:** Never pass `tools.func_id`'s `identified_functions.json` to `--seed-functions`.
5. **Load XBE in Ghidra (`ghidra-xbe`) + Optional Dynamic `xemu` Seeding**
   - Import a read-only copy of `default.xbe` with `XboxDev/ghidra-xbe` (pinned Ghidra `12.1.x+`) and parse `mborgerson/xbox-includes` (`xbox.h`) if analyzing complex structs.
   - If using AI/MCP tools (`REA`, `ReVa`, `ghidra-mcp`), run read-only against a project copy and cap confidence at `<= medium` in `reports/port.db`.
   - Optionally boot the user's dump in `xemu` (GDB stub) to verify runtime basic blocks or tricky vtable dispatches.

## Exit Gate
- [ ] All code sections identified (not just `.text`), plus `XbSymbolDatabase` symbols extracted.
- [ ] Engine/middleware, RTTI anchors, and vtable seed list (`seed_functions.json`) recorded.
- [ ] `reports/port.db` populated with functions, xrefs, and honest confidence tags.
