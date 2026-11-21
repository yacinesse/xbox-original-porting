# Tool Guide: `xboxrecomp` Pipeline & Runtime Usage

`sp00nznet/xboxrecomp` (MIT runtime + LGPL-2.1+ extracted `xemu` NV2A/APU cores) is the primary recommended toolchain for **Original Xbox static recompilation on Windows (`D3D11`), especially for `D3D8LTCG` or pushbuffer-driven titles**.

## 1. Prerequisites & Cloning

- Python 3.10+ with `capstone` (`py -3 -m pip install capstone`).
- CMake `>= 3.20`, Ninja, and either **Visual Studio 2022 (MSVC)** or **WinLibs MinGW-w64 GCC + GDB** (`-O3 -fno-math-errno`).
- Clone into an external tools directory (keep your game project in a separate sibling directory):
  ```powershell
  git clone https://github.com/sp00nznet/xboxrecomp.git Tools/external/xboxrecomp
  ```

## 2. Static Analysis & Lifting Commands (Verified Flags)

> **Important:** `tools.disasm` auto-reads `<xbe_stem>_analysis.json` in the same folder as `default.xbe` unless `--analysis-json` is specified.

```powershell
# Run from inside your xboxrecomp root (or pass PYTHONPATH)
Push-Location Tools/external/xboxrecomp

# 1. Parse XBE structure, sections, and kernel ordinals (required by step 2)
py -3 -m tools.xbe_parser ../../../Extracted/default.xbe `
    --json ../../../Extracted/default_analysis.json

# 2. Disassemble ALL code sections (omit --text-only for XDK/BINK/D3D sections!)
#    Pass --extra-sections XIPS,DOLBY if sections lack the XBE Executable flag.
#    Repeat --seed-functions for hand-cured or vtable-scanned seed JSON files.
py -3 -m tools.disasm ../../../Extracted/default.xbe --force `
    --seed-functions ../../../Research/seed_functions.json `
    -o ../../../Research/disasm

# 3. Classify functions (CRT, D3D, RenderWare, vtables)
py -3 -m tools.func_id ../../../Extracted/default.xbe `
    --functions ../../../Research/disasm/functions.json `
    --strings   ../../../Research/disasm/strings.json `
    --xrefs     ../../../Research/disasm/xrefs.json `
    --output    ../../../Research/disasm/identified.json

# 4. Recover calling conventions and parameter counts
py -3 -m tools.abi_analysis ../../../Extracted/default.xbe `
    --functions  ../../../Research/disasm/functions.json `
    --identified ../../../Research/disasm/identified.json/identified_functions.json `
    --output-dir ../../../Research/disasm/abi

# 5. Lift all functions to split C files, excluding manual overrides safely
py -3 -m tools.recomp ../../../Extracted/default.xbe `
    --game-name "MyXboxGame" --all --split 1000 `
    --disasm-dir ../../../Research/disasm `
    --identified ../../../Research/disasm/identified.json/identified_functions.json `
    --abi        ../../../Research/disasm/abi/abi_functions.json `
    --exclude-manual ../../../RecompPort/src/recomp_manual.c `
    --gen-dir    ../../../Source/Recompiled

Pop-Location
```

### Critical CLI Pitfalls & Guardrails
- **Never feed `identified_functions.json` to `--seed-functions`!** It contains signature-inferred addresses that can sit mid-instruction inside existing functions, clamping them before their epilogues.
- **Avoid `--text-only` on `D3D8LTCG` / multi-section XBEs:** Sections like `D3D`, `D3DX`, `DSOUND`, `XACTENG`, `XPP`, `BINK*`, and `WMADEC` contain critical executable code.
- **Use `--exclude-manual path/to/recomp_manual.c`:** Keeps manual merged functions (`sub_XXXXXXXX`) and `sub_XXXXXXXX_gen` wrappers synchronized automatically across regenerations.
- **Keep `--split 250` to `--split 1000`:** Parallel Ninja builds (`-j8`) compile split files in ~1–2 minutes; monolithic outputs exhaust RAM/time.

## 3. Essential Runtime Environment Switches

Note that many `xboxrecomp` environment checks test `getenv("VAR") != NULL` — **unset** a switch to turn it off, do not set `"0"`.

| Variable | Effect / When to Use |
|---|---|
| `RECOMP_PB_EXEC=1` | Enable NV2A pushbuffer execution (required for `D3D8LTCG` / custom backends) |
| `RECOMP_PB_WALK=segment` | Default safe segment walk; use `dma` only if `NO_OPERATION` IRQ interrupt wakeup is wired |
| `RECOMP_FLIP_PACING=0` | Disable `0xFD100410` flip hold when stalling on buffer swaps |
| `RECOMP_TITLE_KEVENTS=1` | Allow title KEVENT synchronization |
| `RECOMP_AC97_READY=1`, `RECOMP_USB=1`, `RECOMP_KEYBOARD=1` | Advertise AC97 audio readiness, MCPX OHCI USB ports, and keyboard port-0 pad |
| `RECOMP_STRIP_ALT_WINDING=1` | Swap `(i+1, i)` on odd triangle-strip faces for culling hardware parity |
| `RECOMP_PB_SCAN=1`, `RECOMP_PB_EXEC_VERBOSE=1` | Survey unhandled NV2A methods or trace initial pushbuffer batches |
| `RECOMP_VSH_CHECK=1` | Run Win64 VSH JIT differentially against reference interpreter (mandatory after JIT edits!) |
| `RECOMP_D3D11_PROF=1`, `RECOMP_PB_REPORT_MS=2000` | Print periodic pushbuffer/VSH timing and FPS diagnostics |
| `RECOMP_WATCHDOG_SECS=30` | Capture guest register/PC dump if main thread stops making progress |
