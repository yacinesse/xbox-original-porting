# Troubleshooting: Boot, XISO, XBE & Startup Crashes

## 1. Windows Explorer Launch: `"Failed to load default.xbe"`

- **Symptom:** Running the compiled `.exe` from your terminal succeeds, but double-clicking it in Windows Explorer (or via a shortcut in `Builds/` or `bin/`) immediately pops up an error dialog saying it cannot find `default.xbe` or game assets.
- **Cause:** Windows Explorer sets the process Current Working Directory (`CWD`) to the directory containing the `.exe` (`Builds/recomp_build/`), or Git Bash passes a POSIX path (`/d/myport`), whereas the game opens `default.xbe`, `D:\...`, and asset archives relative to CWD.
- **Verified Fix:** At the top of `WinMain` / `main` (see [recomp_main_template.c](../examples/recomp_main_template.c)), call `GetModuleFileNameA(NULL, ...)` and walk up parent folders (up to 4–6 levels) checking for `default.xbe` or `game\default.xbe`, then call `SetCurrentDirectoryA(...)`.

## 2. Immediate Crash Calling Code Outside `.text`

- **Symptom:** The guest jumps or calls into a valid XBE address inside `D3D`, `D3DX`, `DSOUND`, `XACTENG`, `XPP`, `BINK*`, or `XONLINE`, hitting `NULL` or unlifted stub behavior.
- **Cause:** Disassembly ran with `--text-only`, or a code-holding section lacked the XBE `Executable` flag (`0x04`).
- **Verified Fix:**
  1. Run `scripts/xbe_inspect.py default.xbe` and inspect **all 30+ sections** (`flags_str` containing `X` plus library names like `BINK*`, `XIPS`, `DOLBY`).
  2. Omit `--text-only` in `tools.disasm`, and explicitly pass `--extra-sections ...` for any non-flagged code section.

## 3. Crash / Silent Failure on `0x80000000+` Mirror Writes

- **Symptom:** Title writes texture, pushbuffer, or scratch data via `0x80000000+` physical/contiguous aliases, and either crashes or reads stale zeros at the base virtual address.
- **Cause:** Using separate `VirtualAlloc` + `memcpy` buffers instead of true shared-page aliases.
- **Verified Fix:** Use `CreateFileMappingA` + multiple `MapViewOfFileEx` views pointing to the exact same section object (handled by `xboxrecomp`'s `xbox_MemoryLayoutInit()`).

## 4. VEH Handler Breaking Game C++ / SEH Logic

- **Symptom:** Game throws C++ exceptions or intentional integer divide-by-zero / float guards inside protected blocks, then corrupts state instead of taking its `__except` path.
- **Cause:** A blanket Vectored Exception Handler swallowed `EXCEPTION_INT_DIVIDE_BY_ZERO` or generic access violations before SEH could unwind.
- **Verified Fix:** Only return `EXCEPTION_CONTINUE_EXECUTION` from your VEH when `xbox_VehMmioFault(ep)` recognizes an emulated hardware MMIO region (`0xFD000000` NV2A, `0xFEC00000` MCPX APU, `0xFED00000` OHCI).

## 5. XISO / XBE Inspection Failures

| Symptom | Cause | Fix |
|---|---|---|
| `MICROSOFT*XBOX*MEDIA` not found | Redump full XGD1/XGD2/XGD3 image or `.cci`/`.cso` compressed image | Use `scripts/xiso_inspect.py` (auto-probes `0x0`, `0x18300000`, `0x0FD90000`, `0x02080000`); decompress `.cci`/`.cso` first with `Repackinator` |
| `Build Type: UNKNOWN` | Non-standard image base or Chihiro/Debug XOR key | Verify against Retail (`0xA8FC57AB`), Debug (`0x94859D4B`), and Chihiro (`0x40B5C16E`) keys in `xbe_inspect.py` |
| `SHA1=FAIL` or `SHA1=ZERO` | `ZERO` = normal for `nxdk`/`cxbe` homebrew; `FAIL` = patched retail `.xbe` | Re-extract an unmodified retail `default.xbe` before lifting |

## 6. Windows Explorer Launch Fails: `"libwinpthread-1.dll was not found"` (MinGW-w64)

- **Symptom:** Binary runs cleanly in a developer shell (where WinLibs MinGW `bin/` is on `PATH`), but double-clicking it in Windows Explorer pops up a Windows System Error for `libwinpthread-1.dll`, `libgcc_s_seh-1.dll`, or `libstdc++-6.dll`.
- **Root Cause:** Passing `-Wl,-Bstatic -lwinpthread` in CMake `target_link_options` is NOT sufficient—GCC appends implicit runtime link libraries afterward, still linking `libwinpthread-1.dll` dynamically.
- **Verified Fix:** Pass **`-static -static-libgcc`** in `target_link_options` (see [CMakeLists.port.example](../examples/CMakeLists.port.example)), then run `py -3 scripts/verify_port_release.py <exe> --test-explorer 12` to confirm **0 non-OS DLL imports** and a clean launch from `C:\Windows\Temp` with `PATH` stripped to `System32`/`Windows`.
