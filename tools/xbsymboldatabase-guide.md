# Tool Guide: `XbSymbolDatabase` (`XbSymbolDatabaseCLI`)

`Cxbx-Reloaded/XbSymbolDatabase` (MIT) scans retail or `D3D8LTCG` Original Xbox `.xbe` binaries using OOVPA byte patterns to recover exact XDK library symbols, globals, and render-state tables.

## 1. When to Use `XbSymbolDatabase`

- Immediately after extracting `default.xbe` to locate internal XDK structures that static disassembly cannot name — especially **`D3D8LTCG__D3D_g_pDevice`** (needed for `xbox_Nv2aMirrorFence`), `DSOUND__CMcpxAPU_*` helpers, `XAPILIB` initialization helpers, and D3D render-state variable addresses (`D3DRS_*`).
- Inside Ghidra automatically via `XboxDev/ghidra-xbe`, OR standalone from CLI (`XbSymbolDatabaseCLI.exe`) when driving `xboxrecomp` pipelines.

## 2. Building `XbSymbolDatabaseCLI` on Windows (CMake + Ninja)

```powershell
git clone https://github.com/Cxbx-Reloaded/XbSymbolDatabase.git Tools/external/XbSymbolDatabase
cmake -S Tools/external/XbSymbolDatabase -B Builds/xbsym -G Ninja
cmake --build Builds/xbsym
```

*(Built and verified on Windows with WinLibs MinGW GCC 16.2.0 + CMake/Ninja; also supports MSVC.)*

## 3. Running Symbol Extraction Safely

```powershell
.\Builds\xbsym\projects\cli\XbSymbolDatabaseCLI.exe Extracted\default.xbe > Research\xbe_symbols.txt
```

### How to Use Recovered Symbols Without Breaking Disassembly

1. **Locate Key Globals & Entry Points (`_g_pDevice`, `DSOUND_*`, `XPP_*`):**
   - Search `xbe_symbols.txt` for `D3D_g_pDevice` to get the exact static device struct VA for pushbuffer/fence debugging (`xbox_Nv2aMirrorFence`).
   - Search `DSOUND__CMcpxAPU` or `XACTENG` symbols to verify crash/hang backtraces inside static `recomp_*.c` code.
2. **Label Functions in Analysis Databases (`port.db` / `functions.json`):**
   - Match symbol addresses against detected starts in `functions.json`.
   - **Caution:** Do **NOT** blindly dump every `XbSymbolDatabase` address into `xboxrecomp --seed-functions` if an OOVPA hit matches a library helper fragment or mid-body offset inside a larger LTCG function — always cross-check against `functions.json` ranges first (`scripts/scan_vtables.py` demonstrates interior-range blocking).
