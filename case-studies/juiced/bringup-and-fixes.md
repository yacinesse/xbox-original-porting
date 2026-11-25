# *Juiced* Case Study: Bring-Up Stalls & Codegen Fixes

This document captures the exact boot blockers, stalls, and disassembly/lifter issues solved while bringing *Juiced* from initial boot to stable menu and race execution.

## 1. Disassembly & Indirect Call Recovery ([VERIFIED])

### Missing `.rdata` Vtable Targets (`163` Seeds)
- **Symptom:** Runtime crashes or missing subsystem init on `RECOMP_ICALL` lookups returning `NULL` (e.g., `0x00136F40`, `0x001885D0`, `0x00136FD0`, `0x002051D0`).
- **Root Cause:** Static recursive descent missed indirect virtual methods referenced only through `.rdata` vtable arrays (`732` vtables identified overall).
- **Fix:** Scanned `.rdata` pointer tables (`scripts/scan_vtables.py` formalizes this pattern), seeded **156** missed `.rdata` vtable methods plus **7** runtime-observed `ICALL` targets (**163** total seeds in `seed_functions.json`) via `--seed-functions`.
- **Recomp Rule Verified:** NEVER pass `func_id`'s `identified_functions.json` directly into `--seed-functions` — interior boundary guesses split existing functions mid-body.

### Mid-Instruction Function Splits (`recomp_manual.c` Fixes)
- **Symptom 1 (Boot/Resource Load Failure):** `sub_00137210` was split by static boundary detection at `0x0013722A`, corrupting stack depth (`-32` byte `esp` shift) and clobbering `edi` during resource ID `0x10007` lookup.
- **Symptom 2 (Save Screen Crash):** `sub_0001BE80` was split at `0x0001BFD9`, crashing on the `SAVING...` screen (`CMSGlobal.sav`).
- **Additional Split/Manual Functions Merged:** `sub_000B6210`, `sub_0014D380`, `sub_00179A70`.
- **Durable Fix:** Merged complete function bodies in `RecompPort/src/recomp_manual.c` and hooked them in `recomp_lookup_manual()` so re-running the lifter with `--exclude-manual` preserves overrides cleanly.

## 2. `D3D8LTCG` & Kernel/MMIO Hang Fixes ([VERIFIED])

| Blocker | Symptom | Root Cause | Verified Solution |
|---|---|---|---|
| **Missing D3D Fence Advance** | Hang during early device init (`0.00 fps`, `0 flips`) | `D3D8LTCG` polls software/GPU fence counters off `D3D_g_pDevice` (`0x002BC378`) | Call `xbox_Nv2aMirrorFence(0x002BC378u, 0x2Cu, 0x30u)` so NV2A thread keeps pace |
| **DMA Walk `KEVENT` Freeze** | Title hangs in `KeWaitForSingleObject` (`KEVENT 0x002BBC9C`) after opening pushbuffer | Under `RECOMP_PB_WALK=dma`, `BlockOnTime` (`sub_002AE5D0`) sees lag, patches software `NV097_NO_OPERATION` (`0x40100`), and waits for an interrupt not yet delivered | Use `RECOMP_PB_WALK=segment` (with `RECOMP_TITLE_KEVENTS=1`) unless interrupt delivery is wired |
| **Flip-Hold Stall** | Stall around `143–319` flips on title/warning flow | `sub_002AEA40` spins on `0xFD100410` while `nv2a_ack_thread` holds `flip_held` | Set `RECOMP_FLIP_PACING=0` |
| **MCPX APU Poll Infinite Loop** | Intermittent `0.00 fps` stall (`134–2,119` flips into attract/Bink) with GPU/vblank threads still alive | `gdb --batch` caught Thread 1 in `sub_00280CC7` (`loc_00280CFD`, called from `DSOUND__CMcpxAPU_ServiceDeferredCommandsLow` at `0x0027AA7E`) testing `& 2` on `0xFEC0010B` (`eax - 20971253`) without re-reading or timing out | Bounded MMIO re-read loop (`for (int _apu_spin = 0; _apu_spin < 1000; _apu_spin++)` checking `MEM8(...) & 2`) |
| **DSP Watchdog 10 ms Stall** | `10 ms` per-frame CPU pause | `DSOUND` (`sub_0027A83E` at caller `0x0027A905`) calls `KeStallExecutionProcessor` polling GP DSP watchdog `0xCCCCCC` despite instant emulated MMIO | Short-circuit `xbox_KeStallExecutionProcessor` when `g_xbox_kernel_caller == 0x0027A905u` |
| **Missing MMIO/USB VEH Handlers** | Crash on APU/OHCI/NV2A MMIO reads or missing controller enumeration | Host WinMain lacked Vectored Exception Handler & OHCI init | Install `xbox_VehMmioFault(ep)` first in VEH; call `xbox_OhciInit()`; set `RECOMP_AC97_READY=1`, `RECOMP_USB=1`, `RECOMP_KEYBOARD=1`, `RECOMP_VBLANK=1` |
| **Cold-Boot Title `KEVENT` Race Under `-O3`** | Rare flip-0 hang waiting on title KEVENT `0x002BBC8C` | Non-volatile `BRIDGE_MEM32` read in `ke_guest_event_prepare()` lacked memory barrier between `ResetEvent` and guest `SignalState` re-read | Use `volatile uint32_t *` + `MemoryBarrier()` in `ke_guest_event_prepare()` (`kernel_bridge.c`) |

## 3. Standalone Windows Explorer Launch & Save Persistence ([VERIFIED])

- **CWD Auto-Discovery:** `main.c` resolves the `.exe` folder via `GetModuleFileNameA`, walks up parent directories until finding `default.xbe` (or `game\default.xbe` / `private\extracted\disc\default.xbe`), configures sibling writable `saves\`, and calls `SetCurrentDirectoryA`.
- **Zero Non-OS DLL Imports (MinGW-w64):** Passing `-Wl,-Bstatic -lwinpthread` alone STILL dynamically imported `libwinpthread-1.dll`; switching `target_link_options` to **`-static -static-libgcc`** reduced imports strictly to stock Windows OS DLLs. Verified cleanly by launching `juiced_recomp.exe` from `C:\Windows\Temp` with `PATH` stripped to `C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem` (`EXIT=0`, `[FAST-TLS]` verified, 210,062 draws / 419,577 triangles).
- **`UDATA`/`TDATA` Save Persistence:** Created `Player` profile in-game → wrote `saves\UDATA\545100ef\B36B6776DA41\{juicey.dat (51,049 B), SaveMeta.xbx, saveimage.xbx, signature (20 B)}` with 0 crashes and reloaded cleanly on subsequent boots (`NTSTATUS 0x00000000`).
