# Game Engine, Runtime & Kernel Integration

This reference covers integrating statically recompiled Xbox code with kernel shims, filesystem mappings, threading, `D3D8LTCG` runtime plumbing, and architecture trade-offs.

## 1. Static Recompilation vs. Clean-Room Reimplementation

| Approach | Strengths | Risks & When to Avoid |
|---|---|---|
| **Static Recompilation (`xboxrecomp` / `XboxXBERecomp`)** | Preserves 100% authentic UI, menus, state machines, car/character physics, audio banks, and shaders directly from the original XBE. | Requires resolving LTCG symbols, `ICALL`/vtable seeds, mid-instruction splits, and pushbuffer/HLE quirks. |
| **Clean-Room C++ / D3D12 Reimplementation** | Clean modern codebase when only asset formats or open source scripts matter. | **High Failure Risk for Full Game Ports:** Recreating menus, HUD transitions, physics edge cases, camera math, and bespoke shaders from scratch takes months and easily diverges from the original game experience (see *Juiced* clean-room pivot). |

**Rule of Thumb:** Choose **Static Recompilation** first for commercial closed-source Xbox titles unless official source code is available.

## 2. `xboxrecomp` Host Integration (`main.c`, `recomp_manual.c`, `Nv2aBackend`)

Keep your game project in its own directory referencing an external pinned `xboxrecomp` checkout (`examples/CMakeLists.port.example`):

1. **Startup CWD Resolution (`recomp_main_template.c`):** Walk up from `GetModuleFileNameA` looking for `default.xbe` so double-clicking in Windows Explorer never fails with missing assets.
2. **VEH MMIO Trap:** Register `AddVectoredExceptionHandler` delegating solely to `xbox_VehMmioFault(ep)` (NV2A/APU/OHCI). Never trap game SEH/`DIV0`.
3. **Device / Pushbuffer Init (`D3D8LTCG`):**
   - Enable `RECOMP_PB_EXEC=1`, `RECOMP_PB_WALK=segment`, `RECOMP_FLIP_PACING=0`, `RECOMP_AC97_READY=1`, `RECOMP_USB=1`, `RECOMP_KEYBOARD=1`.
   - Initialize `xbox_OhciInit()`.
   - Locate `D3D8LTCG__D3D_g_pDevice` via `XbSymbolDatabaseCLI` and mirror submitted/consumed fences (`xbox_Nv2aMirrorFence(g_pDevice_va, 0x2Cu, 0x30u)` after verifying offsets for your XDK build).
   - Register your hardware D3D11 backend (`nv2a_d3d11_init_backend()`) before launching the guest thread.
4. **Durable Overrides (`recomp_manual.c` + `--exclude-manual`):**
   - Implement `recomp_lookup_manual(uint32_t xbox_va)` and override split functions or unbounded MMIO poll loops cleanly here so re-lifting with `tools.recomp --exclude-manual` never overwrites patches.

## 3. Kernel Ordinal Layer (`xboxkrnl.exe`)

All Xbox kernel calls are imported strictly by ordinal (`1`–`378`).
- **Rule: Never use silent no-ops.** Log rate-limited warnings with ordinal number, name, and `g_xbox_kernel_caller`, increment counters, and track implementation status in `reports/port.db` (`scripts/init_port_db.py`).
- **Core Tier 0 Groups:**
  - **Memory:** `MmAllocateContiguousMemory*`, `MmFreeContiguousMemory`, `MmGetPhysicalAddress`, `NtAllocateVirtualMemory`, `NtFreeVirtualMemory`, `ExAllocatePool*`.
  - **File I/O:** `NtCreateFile`, `NtOpenFile`, `NtReadFile`, `NtWriteFile`, `NtQueryInformationFile`, `NtQueryDirectoryFile`, `NtClose`, `IoCreateSymbolicLink`.
  - **Threading & Sync:** `PsCreateSystemThreadEx` (each thread gets its own `g_fs_base` TIB and `RecompThreadState`!), `KeInitializeEvent`, `KeSetEvent`, `KeWaitForSingleObject`, `KeWaitForMultipleObjects`, `RtlInitialize/Enter/LeaveCriticalSection`, `KeDelayExecutionThread`.
  - **System / Clocks / EEPROM:** `KeQueryPerformanceCounter`, `KeQueryPerformanceFrequency`, `KeQuerySystemTime`, `KeTickCount`, `HalReadSMCTrayState` (`0x10` media present), `ExQueryNonVolatileSetting`, `KeStallExecutionProcessor` (watch for DSP busy-wait callers!).

## 4. Filesystem, Drive Mapping & Multi-XBE

| Xbox Path / Drive | Meaning | Host Mapping |
|---|---|---|
| `\Device\CdRom0\`, `D:` | Optical disc / game root | Read-only game data directory (`default.xbe` root) |
| `T:` / `U:` | Title / User persistent data (`TDATA`, `UDATA`) | Writable user save directory (`saves/TDATA/`, `saves/UDATA/`) |
| `Z:`, `X:`, `Y:` | Utility & cache partitions (heavily used by streaming titles!) | Writable cache directory (`cache/Z/`, etc.) |

- **Multi-XBE Switching (`XLaunchNewImage`):** Map secondary `.xbe` names to recompiled modules/launch arguments while preserving `LaunchDataPage`. Note that `dashupdate.xbe` / `update.xbe` are system updaters and not needed for gameplay.

## 5. Common Middleware Fingerprints

| Middleware | Indicators in `.xbe` / Assets | Porting Notes |
|---|---|---|
| **RenderWare** | `RwEngineInit`, `.rws`, `.dff`, `.txd` | Well-documented (`aap/librw`); `xboxrecomp` has built-in patterns. |
| **Unreal Engine 2** | `Core.dll` strings, `.utx`, `.usx`, `UCC` | Heavy C++ vtables (`UObject`, scan `.rdata`!); inspect with `UEViewer`. |
| **Havok** | `hkWorld`, `Havok` copyright strings | Sensitive to x87 precision/rounding mode—validate physics carefully. |
| **Gamebryo / NetImmerse** | `NiDX8Renderer`, `.nif`, `.kf` | Clean D3D8 abstraction; inspect with `NifSkope`. |
| **Bink / Miles / XACT** | `BINK*` sections, `XactSounds.xsb`, `.xwb` | Bink runs natively in `xboxrecomp` pushbuffer builds; check `0x0027A905`-style DSP stalls and YUY2 texture hashing. |
