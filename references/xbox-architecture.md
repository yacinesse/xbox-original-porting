# Original Xbox Hardware & System Architecture

This reference summarizes the hardware and OS architecture of the Original Xbox (2001–2005) as it directly affects PC porting, static recompilation, and HLE runtime design.

## 1. Core Hardware Specifications

| Subsystem | Original Xbox Specification | Porting Impact |
|---|---|---|
| **CPU** | Custom Intel Pentium III ("Coppermine"-derived), 733 MHz, 32-bit x86 (`i686`) | Supports x87, MMX, SSE (no SSE2+). Games often rely on x87 80-bit/53-bit/24-bit precision control and `rdtsc` / 733 MHz timing assumptions. |
| **Memory** | 64 MB unified DDR SDRAM (`0x00000000`–`0x03FFFFFF`; 128 MB on Debug/Devkit units) | Shared CPU/GPU unified memory architecture (UMA). Textures, vertex buffers, and NV2A pushbuffers live directly in main RAM. |
| **GPU** | NVIDIA NV2A (233 MHz, GeForce 3/4 Ti-derived) | Fixed-function T&L + programmable vertex shaders (136-bit microcode) + NV2A register combiners + `0xFD000000` MMIO control registers. |
| **Audio** | NVIDIA MCPX APU (256-voice hardware mixer + Motorola 56300-derived GP/EP DSPs) | DirectSound8 + XACT APIs statically linked; MMIO at `0xFEC00000`; hardware Xbox ADPCM and DSP effects. |
| **USB / Input** | Dual OHCI USB 1.1 host controllers (`0xFED00000`+) + XID gamepad protocol | Statically linked `XPP`/`XAPI` polls OHCI ports/interrupts unless overridden at API boundary; analog face buttons `0..255`. |
| **Storage** | 8/10 GB IDE HDD (FATX) + DVD-ROM (XDVDFS) | Read-only disc paths (`\Device\CdRom0`, `D:`) and writable HDD/title-data partitions (`T:`, `U:`, `Z:`, `E:`). |
| **OS / Kernel** | Custom stripped-down Windows 2000-derived kernel (`xboxkrnl.exe`) | Single-process, physical/contiguous memory model, no virtual paging, kernel exports imported **by ordinal only** (`1`–`378`). |

## 2. Address Space, Mirrors & Hardware MMIO Windows

Original Xbox executables are 32-bit and bake in absolute 32-bit addresses (`uint32_t`).

- **Default XBE Base Address:** Typically `0x00010000`.
- **Contiguous / Physical / GPU Aliases:** Physical RAM (`0x00000000`–`0x03FFFFFF`) is aliased into cached, uncached, and write-combined windows (e.g., `0x80000000+` system/contiguous aliases).
- **Hardware MMIO Regions (VEH Trap Boundaries on Windows):**
  - `0xFD000000+`: **NV2A GPU** control, PGRAPH, PCRTC, PFIFO (`DMA_PUT` / `DMA_GET`), and VBlank registers.
  - `0xFEC00000+`: **MCPX APU** voice/DSP registers and doorbell status bits (e.g., `0xFEC0010B` `& 2`).
  - `0xFED00000+`: **OHCI USB** host controller registers polled by `XPP`/`XAPI`.
  - **Host Trap Strategy (`xbox_VehMmioFault`):** On Windows, unmapped MMIO regions trigger `STATUS_ACCESS_VIOLATION`, caught by a narrow **Vectored Exception Handler (VEH)** that decodes the faulting load/store into hardware emulation. *Never* intercept general exceptions like `DIV0` in the same handler, or title SEH `__except` recovery breaks.
- **Pointer Width Constraint:** In a 64-bit Windows host port (`x86_64`), guest pointers stored inside guest RAM **must remain 32-bit** (`uint32_t` / `guest_ptr`). Never serialize a 64-bit host `void*` into guest memory.
- **Host Mapping Strategies (Choose via ADR):**
  1. **File-Mapping Mirror Views (`CreateFileMapping` + `MapViewOfFileEx`):** Maps the **exact same physical pages** at multiple virtual addresses (`xboxrecomp` uses ~28 mirror views covering `0x00000000` and `0x80000000+` aliases) so writes through one alias immediately appear in the other. `VirtualAlloc` + `memcpy` does **NOT** alias physical pages and causes silent coherence bugs.
  2. **Base-Offset Translation:** Reserve a contiguous guest region and add `g_xbox_mem_offset` on every memory macro (`MEM32(va)`). Safe under strict Win64 ASLR.

## 3. CPU Semantics, TLS Registers & Pitfalls

### Global Thread-Local Register Model & Win64 `RECOMP_FAST_TLS`
- Static recompilers represent guest registers (`g_eax..g_edi`, `g_esp`, `g_ebp`, `g_fs_base`, x87 stack, XMM0–7) as thread-local storage so each guest thread (`PsCreateSystemThreadEx`) stays isolated.
- **MinGW-w64 / GCC Performance Trap:** Standard `__thread` / `_Thread_local` compiles on Win64 MinGW into `__emutls_get_address` function calls on nearly every register read/write, crippling FPS. Packing all guest registers into one struct referenced via a single `TlsAlloc()` slot read directly from the x86-64 `%gs:` TEB (`RECOMP_FAST_TLS`) reduces register access to a single instruction.

### x87 Floating-Point Unit & SSE
- Xbox configures the x87 FPU Control Word (`FLDCW`) for **24-bit** (single) or **53-bit** (double) precision rather than 80-bit extended precision, and supports **SSE1** + **MMX** (no SSE2/AVX).
- Validate physics, camera math, and `MXCSR` FTZ/DAZ or `cvttss2si` truncation with differential checks (`RECOMP_VSH_CHECK=1` for vertex shaders, `xemu` traces for guest CPU).

### Segment Registers & SEH
- **`FS` Register:** Points to the Xbox KPCR/TIB. `fs:[0]` holds the Structured Exception Handling (SEH) frame chain.
- MSVC-compiled games use `__SEH_prolog` / `__SEH_epilog`; lift/bridge `fs:[x]` accesses via per-thread `g_fs_base` and keep `g_seh_ebp` synchronized.

### Timing & Clocks
- `KeQueryPerformanceCounter` runs at **1.193182 MHz** (`rdtsc` ~**733.33 MHz**); `KeTickCount` increments every `1 ms`.
- Scale delta-time properly or pace cutscenes/FMVs against monotonic host time so uncapped FPS does not speed up gameplay.

## 4. Statically Linked XDK Architecture

Unlike Windows PC games that dynamically link `d3d8.dll` or `dsound.dll`, Original Xbox games **statically link** all XDK libraries (`D3D8`/`D3D8LTCG`, `DSOUND`, `XAPILIB`, `XNET`, `XONLINE`, `XACT`, `LIBCMT`) directly into `.xbe` sections.
- **Only `xboxkrnl.exe` is dynamically imported**, strictly **by ordinal** (`1`–`378`).
- Because XDK calls are compiled directly into the binary, you must either:
  1. **Signature-match XDK functions** (`XbSymbolDatabase` / FID) and intercept at the C API boundary (`D3D8` HLE), **or**
  2. **Lift XDK sections intact and execute at the hardware/pushbuffer boundary** (`xboxrecomp` `RECOMP_PB_EXEC=1` + MCPX APU + OHCI USB), required whenever **`D3D8LTCG`** inlines D3D calls into register-calling mega-functions.
