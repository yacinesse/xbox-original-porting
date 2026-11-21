# Verified GitHub Repositories & Ecosystem Projects

> Consolidated reference inventory verified via GitHub HTTP/API inspection and live tool checkouts. See also concise workflow summaries in [tools-and-repositories.md](../references/tools-and-repositories.md).

## 1. Static Recompilation Toolkits & Related Architectures

| Project | URL | License | Key Capabilities |
|---|---|---|---|
| **xboxrecomp** | `https://github.com/sp00nznet/xboxrecomp` | MIT *(runtime)* / LGPL-2.1+ *(`xemu` NV2A/APU)* | Title-agnostic Python pipeline (`xbe_parser`, `disasm`, `func_id`, `abi_analysis`, `recomp`) + C runtime (`xbox_kernel`, `xbox_d3d8`, `xbox_nv2a` pushbuffer executor, `xbox_apu`, `xbox_usb`, `xbox_input`). Tested through `v0.17.0` (`Empty Promises`, Nov 2026). |
| **xboxrecomp-cli (`xbr`)** | `https://github.com/apexJCL/xboxrecomp-cli` | Check upstream | `game.toml`-driven wrapper around `xboxrecomp` for pinned toolchains, cross-builds, and packaging. |
| **XboxXBERecomp** | `https://github.com/TGP482/XboxXBERecomp` | MIT | C++/Zydis static recompiler + D3D12 + XAudio2 + SDL3 runtime (best suited when XDK D3D8 symbols match `>= 90%`). |
| **SCDA-XBERecomp** | `https://github.com/TGP482/SCDA-XBERecomp` | MIT | Reference commercial port on `XboxXBERecomp`. |
| **xbox-pc-porting-guide** | `https://github.com/terellison/xbox-pc-porting-guide` | Unspecified | Guide, `xboxport` CLI, *Ninja Gaiden Black* case study. |
| **N64Recomp / XenonRecomp / RexGlueSDK** | `https://github.com/N64Recomp/N64Recomp`<br>`https://github.com/hedge-dev/XenonRecomp`<br>`https://github.com/rexglue/rexglue-sdk` | MIT | Sister static-recompilation architectures (MIPS / Xbox 360 PPC) demonstrating hook/table/SDK linking patterns. |

## 2. XBE, XDVDFS & Symbol Tooling

| Tool | URL | License | Usage |
|---|---|---|---|
| **XbSymbolDatabase** | `https://github.com/Cxbx-Reloaded/XbSymbolDatabase` | MIT | OOVPA byte signatures for all XDK releases (`D3D8`, `D3D8LTCG`, `DSOUND`, `XAPILIB`, `XONLINE`, `XACTENG`). |
| **xdvdfs** | `https://github.com/antangelo/xdvdfs` | MIT | XISO & XGD1–3 Rust library/CLI (`xdvdfs-cli`). |
| **extract-xiso** | `https://github.com/XboxDev/extract-xiso` | BSD-style | Classic CMake XISO unpacker/packer. |
| **Repackinator** | `https://github.com/Team-Resurgent/Repackinator` | GPL-3.0 | Redump XISO / `.cci` / `.cso` decompression & verification. |
| **pyxbe** / **xbedump** | `https://github.com/XboxDev/pyxbe`<br>`https://github.com/XboxDev/xbedump` | MIT / GPL-2.0 | Reference XBE parsers & SHA-1 section verifiers. |
| **ghidra-xbe** | `https://github.com/XboxDev/ghidra-xbe` | Unspecified | Ghidra XBE loader + auto kernel ordinal labeling + `XbSymbolDatabase`. |

## 3. Emulators, SDKs, Disassembly & Validation Oracles

- **xemu** (`https://github.com/xemu-project/xemu`, GPL-2.0) — Behavioral LLE oracle for NV2A PGRAPH, register combiners, MCPX APU, and GDB stubs.
- **Cxbx-Reloaded** (`https://github.com/Cxbx-Reloaded/Cxbx-Reloaded`, GPL-2.0) — HLE kernel/D3D8 reference semantics.
- **nxdk** (`https://github.com/XboxDev/nxdk`, MIT/mixed) & **abaire/nxdk_pgraph_tests** (MIT) — Legal homebrew build SDK + hardware-verified NV2A PGRAPH golden test suite.
- **abaire/xbdm_gdb_bridge** (MIT) — GDB/NV2A trace capture bridge for hardware verification.
- **Disassemblers / MCP / Debuggers:** `NationalSecurityAgency/ghidra` (Apache-2.0), `zyantific/zydis` (MIT), `capstone-engine/capstone` (BSD), `unicorn-engine/unicorn` (GPL-2.0), `x64dbg/x64dbg` (GPL-3.0), `morluto/rea` (MIT), `cyberkaida/reverse-engineering-assistant` (`ReVa`, Apache-2.0), `bethington/ghidra-mcp` (Apache-2.0), `clearbluejar/pyghidra-mcp` (Apache-2.0), `LaurieWired/GhidraMCP` (Apache-2.0), `symgraph/GhidrAssistMCP` (MIT).

## 4. Reference Community Ports Using `xboxrecomp`

Listed in `sp00nznet/xboxrecomp/README.md` (useful for studying per-title CMake layouts, manual overrides, and renderer patches):
- *Burnout 3: Takedown* (`sp00nznet/burnout3`, v0.12.0 — RenderWare, origin title)
- *007: Nightfire* (`limeylicious/Nightfire-Windows-Port`, v0.8)
- *Jet Set Radio Future* (`andeecollard/jsrf-recomp`, v0.8.0 fork)
- *Def Jam: Fight for NY* (`vyanhursky/DefJamFFNY-recomp`, v0.16.0 fork)
- *SSX 3* (`koenhendriks/SSX3-recomp`, v0.13.1 fork; `bertibertig/SSX3-Recomp`, v0.14.0 fork) & *SSX Tricky* (`MatiasRiveraC/SSX-Tricky-PC`, v0.5 fork)
- *Amped 2* (`bertibertig/Amped2-Recomp`, v0.14.0 fork), *BLiNX 2* (`apexJCL/blinx2-recomp`, v0.14.0 fork)
- *Dead or Alive Xtreme Beach Volleyball* (`NoRain211/doaxvb-re`, v0.5 fork), *Kung Fu Chaos* (`maxiumpro/kungfuchaos-recomp`), *Mortal Kombat: Deadly Alliance* (`FOTLabs/mkda-nx`), *StarCraft: Ghost* (`aknavj/scghost-recomp`)
- *(Note: Earlier external URLs `radareorg/r2mcp` and `mborgerson/xbtool` were verified dead/404 and excluded.)*
