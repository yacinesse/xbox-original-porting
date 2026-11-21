# Verified Tools & GitHub Repositories Summary

All repositories below were verified active via GitHub checks or direct checkout inspection (`2026-11`). For full ecosystem project tables and reading links, see [resources/repositories.md](../resources/repositories.md) and [tools/](../tools/xboxrecomp-guide.md).

## 1. Static Recompilation Toolkits

- **xboxrecomp** (`https://github.com/sp00nznet/xboxrecomp`, MIT runtime / LGPL-2.1+ `xemu` NV2A & APU parts) — Primary recommended toolkit on Windows (`v0.17.0` tested). Includes Python XBE/disasm/func_id/ABI/recompiler pipeline and `xbox_kernel` / `xbox_nv2a` pushbuffer executor / `xbox_apu` / `xbox_usb` / `xbox_input` C runtime. **Required when a title uses `D3D8LTCG` or direct pushbuffers.**
- **xboxrecomp-cli (`xbr`)** (`https://github.com/apexJCL/xboxrecomp-cli`) — `game.toml` front-end wrapper for `xboxrecomp`.
- **XboxXBERecomp** (`https://github.com/TGP482/XboxXBERecomp`, MIT) — C++/Zydis static recompiler + D3D12 + XAudio2 + SDL3 runtime (suited for clean `>= 90%` D3D8 API symbol-matched ports; see `TGP482/SCDA-XBERecomp`).
- **xbox-pc-porting-guide** (`https://github.com/terellison/xbox-pc-porting-guide`) — Porting guide, `xboxport` CLI, *Ninja Gaiden Black* case study.
- **N64Recomp / XenonRecomp / RexGlueSDK** (`N64Recomp/N64Recomp`, `hedge-dev/XenonRecomp`, `rexglue/rexglue-sdk`, MIT) — Sister platform static-recompilation references.

## 2. XISO, XBE & Symbol Databases

- **XbSymbolDatabase** (`https://github.com/Cxbx-Reloaded/XbSymbolDatabase`, MIT) — OOVPA byte patterns to recover statically linked `D3D8`/`D3D8LTCG`/`DSOUND`/`XAPILIB`/`XONLINE` globals and helpers (`XbSymbolDatabaseCLI.exe`).
- **xdvdfs** (`antangelo/xdvdfs`, MIT) & **extract-xiso** (`XboxDev/extract-xiso`, BSD) — XISO / XGD1–3 disc tools; **Repackinator** (`Team-Resurgent/Repackinator`, GPL-3.0) for `.cci`/`.cso` Redump handling.
- **pyxbe** (`XboxDev/pyxbe`, MIT) & **xbedump** (`XboxDev/xbedump`, GPL-2.0) — Reference XBE header & SHA-1 parsers.
- **ghidra-xbe** (`XboxDev/ghidra-xbe`) — Ghidra XBE loader with kernel ordinal naming + `XbSymbolDatabase`.

## 3. Oracles, Debuggers & Toolchain

- **xemu** (`xemu-project/xemu`, GPL-2.0) & **Cxbx-Reloaded** (`Cxbx-Reloaded/Cxbx-Reloaded`, GPL-2.0) — Behavioral LLE/HLE emulators; **abaire/nxdk_pgraph_tests** & **XboxDev/nxdk** — Legal homebrew test SDK & hardware-verified NV2A PGRAPH suite.
- **Ghidra** (`NationalSecurityAgency/ghidra`, Apache-2.0; pin `12.1.x+` if using `REA`) + MCP bridges (`morluto/rea`, `cyberkaida/reverse-engineering-assistant`, `bethington/ghidra-mcp`, `clearbluejar/pyghidra-mcp`, `LaurieWired/GhidraMCP`, `symgraph/GhidrAssistMCP` — run read-only after homebrew bake-off!).
- **Windows Toolchain:** Visual Studio 2022 (`MSVC`/`Clang-CL`) OR **WinLibs MinGW-w64 GCC + GDB** (`-O3 -fno-math-errno`, `gdb --batch` hang dumps), CMake `>= 3.20`, Ninja, Python `3.10+` (`capstone` needed for `xboxrecomp`; `scripts/` needs stdlib only).
- **Graphics/Audio/Asset:** **RenderDoc** (`baldurk/renderdoc`), PIX on Windows, **FFmpeg**, **vgmstream**, `aap/librw`, `gildor2/UEViewer`, `niftools/nifskope`, `x64dbg`.
