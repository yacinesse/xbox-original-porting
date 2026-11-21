# Troubleshooting: Freezes, Deadlocks & `0.00 fps` Stalls

When a recompiled Xbox game hangs at `0.00 fps` without crashing, determine **which thread** is stuck before changing any code.

## Step 1: Isolate Guest Spin vs. Host Deadlock (30-Second Triage)

1. Run with watchdog logging (`RECOMP_WATCHDOG_SECS=20` or `30`) to inspect whether the guest thread is executing instructions or blocked in the kernel/host.
2. Attach **`gdb --batch`** (MinGW builds) or capture thread call stacks from **Visual Studio / `x64dbg`** at the moment `0.00 fps` triggers:
   ```powershell
   gdb -p <PID> --batch -ex "set pagination off" -ex "thread apply all bt"
   ```
3. Interpret the stacks:
   - **GPU/VBlank threads still running, guest Thread 1 in `sub_XXXXXXXX`:** Pure guest spin-wait (fence poll, NV2A register poll, or APU MMIO poll).
   - **Guest Thread 1 inside `xbox_KeWaitForSingleObject` / `WaitForSingleObject`:** Kernel event wait that the emulated hardware never signaled.

## Step 2: Match Known Xbox Hang Signatures

### Signature A: Title Spins Waiting for D3D8LTCG Fence Advance
- **Symptom:** Early boot/menu stall at `0` flips inside a D3D section function polling a memory word.
- **Root Cause:** Statically linked `D3D8LTCG` maintains a software submitted-fence counter vs consumed-fence counter inside `D3D_g_pDevice` (e.g., offsets `+0x2C` / `+0x30` in XDK 5849-era titles).
- **Verified Fix:**
  1. Locate `D3D8LTCG__D3D_g_pDevice` using `XbSymbolDatabaseCLI.exe`.
  2. Call `xbox_Nv2aMirrorFence(g_pDevice_va, 0x2Cu, 0x30u)` (verify exact struct offsets in disassembly for your title's XDK build).

### Signature B: Freeze in `KeWaitForSingleObject` Under `RECOMP_PB_WALK=dma`
- **Symptom:** Title progresses through early splashes, then permanently blocks on a `KEVENT` once scene complexity grows.
- **Root Cause:** Under `RECOMP_PB_WALK=dma`, D3D's `BlockOnTime` sees accurate `DMA_GET` lag, patches a software method (`NV097_NO_OPERATION` `0x40100`) into the pushbuffer, and sleeps waiting for a GPU software-method interrupt that the runtime does not deliver.
- **Verified Fix:** Default to **`RECOMP_PB_WALK=segment`** (and `RECOMP_TITLE_KEVENTS=1`) unless your runtime implements NV2A software-method interrupt delivery.

### Signature C: Flip-Hold Stall on `0xFD100410`
- **Symptom:** Stalls after `~100–400` flips inside `D3D` section flip/kickoff wait logic.
- **Root Cause:** `nv2a_ack_thread` skips clearing NV2A busy bit `0x100410` bit 16 when `flip_held` pacing is active.
- **Verified Fix:** Set `RECOMP_FLIP_PACING=0`.

### Signature D: MCPX APU MMIO Spin-Loop (`0xFEC0010B` / `DSOUND`)
- **Symptom:** Intermittent freeze during Bink audio, cutscene transitions, or soundbank streaming while NV2A/vblank threads remain alive. Backtrace lands inside a `DSOUND` deferred-command helper (e.g., `DSOUND__CMcpxAPU_ServiceDeferredCommandsLow` callee) looping on an offset like `0xFEC0010B` (`& 2`).
- **Root Cause:** Guest polls an MCPX APU MMIO register bit expecting hardware clearing, or lifted C cached the MMIO byte before entering the branch loop so subsequent iterations never re-read guest memory.
- **Verified Fix:** Override the polling function in `recomp_manual.c` (with `--exclude-manual`) to explicitly re-read volatile MMIO guest memory inside a **bounded loop** (e.g., max 1,000 iterations) so it breaks safely if hardware ack is asynchronous.

### Signature E: `KeStallExecutionProcessor` DSP Watchdog Busy-Wait
- **Symptom:** Every frame stalls for ~10 ms while calling `KeStallExecutionProcessor` from a `DSOUND` GP DSP watchdog check.
- **Cause:** Because emulated APU MMIO responds synchronously/instantly, `DSOUND` repeatedly enters its retry delay path.
- **Verified Fix:** Identify `g_xbox_kernel_caller` at that call site and fast-return inside `xbox_KeStallExecutionProcessor` only for verified DSP watchdog polling callers.
