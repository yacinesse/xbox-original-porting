# Workflow 4: Code Reconstruction & Iterative Static Recompilation

**Goal:** Lift the game's x86 machine code into fast-compiling, maintainable native C/C++ with durable manual overrides (`recomp_manual.c`), resolved indirect calls (`ICALL`), and clean separation from the upstream toolchain.

## Steps

1. **Validate Pipeline on Homebrew First (`nxdk`)**
   - Before lifting a commercial XBE, compile a small `nxdk` sample XBE (with known symbols/map), lift it, build it natively, and verify it runs cleanly.
2. **Generate Initial Recompiler Configuration (`xboxrecomp` or `XboxXBERecomp`)**
   - **`xboxrecomp`:** Ensure `default_analysis.json` sits beside `default.xbe`, include **all executable/XDK/middleware sections** (omit `--text-only`; pass `--extra-sections ...` if needed), and pass recovered `.rdata` seeds via `--seed-functions`.
   - **`XboxXBERecomp`:** Populate `game.toml` sections, `data_ranges`, `[[switch]]`, and `[symbols]` (`examples/game.toml.example`).
3. **Run the Full Static Lifting Pipeline**
   - Follow the verified sequence (full flags in [xboxrecomp-guide.md](../tools/xboxrecomp-guide.md)):
     1. `xbe_parser` → `<xbe>_analysis.json`
     2. `disasm` (`--force --seed-functions ...`) → `functions.json`, `xrefs.json`, `strings.json`
     3. `func_id` → `identified_functions.json`
     4. `abi_analysis` → `abi_functions.json`
     5. `recomp` → `--all --split 1000 --exclude-manual path/to/recomp_manual.c --gen-dir <game>/src/recomp/gen`
   - **Never commit generated commercial C/C++** to public version control.
4. **Apply Durable Manual Fixes (Mid-Instruction Splits & MMIO Loops)**
   - **Critical Rule:** When a disassembly split (`esp` shift / register clobber) or broken MMIO spin-loop is discovered:
     1. Write the complete fixed/merged function `sub_XXXXXXXX(void)` inside **`src/recomp_manual.c`** (see [recomp_manual_wrapper_example.c](../examples/recomp_manual_wrapper_example.c)).
     2. Register `0xXXXXXXXX` in `recomp_lookup_manual()`.
     3. Re-run `tools.recomp` with `--exclude-manual src/recomp_manual.c` so generated `recomp_NNNN.c` never has duplicate definitions or loses fixes on regeneration.
5. **Configure Fast Native Build (`CMake + Ninja`)**
   - Compile with CMake + Ninja (`-j8`), splitting into ~`250`–`1000` functions per C file (see [CMakeLists.port.example](../examples/CMakeLists.port.example)):
     - **MinGW-w64 / GCC / Clang:** `-O3 -fno-math-errno` (crucial for lifted math & VSH performance!)
     - **MSVC:** `/O2 /GS- /bigobj` (+ `/STACK:8388608`)
   - Verify no unresolved `[UNIMPL]` mnemonics sit inside critical CRT heap or math routines.

## Exit Gate
- [ ] Lifted C compiles cleanly into a native 64-bit `.exe` with 8+ MB thread stack.
- [ ] All `.rdata` vtable seeds and known mid-instruction splits are cleanly excluded via `--exclude-manual`.
- [ ] Build completes incrementally in `< 2 min` without modifying external `xboxrecomp` upstream pipelines unnecessarily.
