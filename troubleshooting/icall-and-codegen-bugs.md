# Troubleshooting: Indirect Calls (`ICALL`), Splits & Codegen Bugs

## 1. `RECOMP_ICALL` Fails or Dispatches `NULL`

- **Symptom:** Logs show `[ICALL] Unknown target 0x00XXXXXX (caller=0x00YYYYYY)` or a subsystem/vtable method never executes.
- **Diagnosis & Fix:**
  1. Check the VA range: addresses outside code sections and kernel thunks (`>= 0x400000 && < 0xFE000000` on standard XBE layouts) indicate an **uninitialized object or corrupted vtable pointer**, NOT a missing function. Inspect the caller struct initialization instead of adding bogus seeds.
  2. If `guest_va` lies inside a valid code section (`.text`, `D3D`, etc.), check `functions.json`:
     - **Not listed:** Run `scripts/scan_vtables.py <default.xbe> --functions disasm/functions.json -o missing_seeds.json` to recover missed `.rdata`/`.data` vtable entries, then append runtime-logged valid `ICALL` targets and re-run `tools.disasm --seed-functions ...`.
     - **CRITICAL HAZARD — Never pass `func_id`'s `identified_functions.json` directly into `--seed-functions`!** Signature matches can point inside an existing prologue/body wrapper, clamping and truncating valid functions before their epilogue (e.g., breaking `__heap_init` on Xbox Dashboard). Always pass raw verified start addresses (like `scan_vtables.py` with `--functions`, which explicitly blocks interior addresses).

## 2. Mid-Instruction Function Splits (Stack Shift & Clobbered Callee-Saved Registers)

- **Symptom:** A game boots past init, then crashes cleanly inside a resource loader, save-game routine (`SAVING...`), or deep subsystem call, with `esp` shifted by `4–64` bytes or `edi`/`esi`/`ebx` holding wrong values.
- **Root Cause:** Static disassembly detected an interior branch target or tail-jump address (`B`) inside function `A` and split `A` into two separate C functions (`sub_A` and `sub_B`). When `sub_A` falls through or jumps into `sub_B`, or when the lifter treats `sub_B` as a fresh function prologue, caller-saved frame depth (`esp`) and callee-saved registers diverge.
- **Verified Fix:**
  1. Inspect both `sub_A` and `sub_B` disassembly around the split address.
  2. Merge the complete contiguous function body for `sub_A` into **`recomp_manual.c`** (or wrap `sub_A`) and hook `0xA` in `recomp_lookup_manual()`.
  3. Rebuild `tools.recomp` with **`--exclude-manual path/to/recomp_manual.c`** so future re-lifting never overwrites your manual fix or regenerates conflicting symbols.
  - *(Never leave permanent hand-edits only in generated `recomp_NNNN.c` files—any `--force` regen wipes them.)*

## 3. Stack Leak After Failed `ICALL`

- **Symptom:** Game runs for ~3–5 minutes, then suffers stack overflow crash (`esp` drifts outside stack bounds).
- **Root Cause:** Caller pushed return address onto simulated stack `g_esp` before `RECOMP_ICALL`, and a failed/no-op lookup failed to clean up `g_esp += 4`.
- **Verified Fix:** Verify `RECOMP_ICALL` pops the dummy return address (`g_esp += 4`) on missing targets, and link with at least an 8 MB host stack (`/STACK:8388608` / `-Wl,--stack,8388608`).

## 4. Subtle Wrong Behavior From Lifted Instructions (`RECOMP_UNIMPL`)

- **Symptom:** Heap allocator returns garbage, bit-masks fail, or physics explodes without any crash.
- **Root Cause:** Unhandled x86 mnemonics (e.g., rare SSE/x87 forms or `bsf`/`bsr` bit scans) emit `RECOMP_UNIMPL` warnings or silent no-ops.
- **Verified Fix:** Check `tools.recomp` summary stderr for unimplemented mnemonics and runtime `[UNIMPL]` logs. Never ignore `RECOMP_UNIMPL` lines in core CRT/engine functions.
