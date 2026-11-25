# Tool Guide: Advanced RE MCP (`rea`) & Automated Win64 Release Tooling

Combine our stdlib Python utilities (`scripts/`) with live Reverse Engineering Assistant (`rea` MCP server) and Win64 automation harnesses for high-velocity, evidence-backed porting.

> **Mandatory Rule Reminder:** Proposals or decompilations from AI/MCP tools (`rea`, Ghidra MCP) remain capped at **`medium`** confidence in `reports/port.db` until verified against raw disassembly xrefs, dynamic traces (`gdb` / `xemu`), or differential checks (`RECOMP_VSH_CHECK=1`).

## 1. Automated Release & Performance Verification (`scripts/`)

### `verify_port_release.py` — Standalone Release & Explorer Gate Auditor
Runs 6 shipping checks in one command with **zero external dependencies** (pure Python PE32/PE32+ parser):

```powershell
# Audit PE imports (0 non-OS DLLs), PE .tls directory, __emutls regressions,
# clean Windows Explorer launch from C:\Windows\Temp, disc SHA-256, and repo hygiene:
py -3 scripts/verify_port_release.py build/recomp/game_port.exe `
    --obj-dir build/recomp/CMakeFiles `
    --test-explorer 12 `
    --manifest reports/disc-manifest.json `
    --extracted private/extracted/disc `
    --repo . `
    --json reports/release-audit.json
```

### `analyze_d3d11_prof.py` — `[D3D11-PROF]` Bottleneck Diagnostician
Parses `[D3D11-PROF]` benchmark logs and automatically flags texture cache hash collisions (`miss >= 5` or `tex >= 1.0 ms`), excessive cubemap face copies (`cube > 12`), active RT self-sampling snapshots (`self > 0`), and guest/VSH CPU bottlenecks:

```powershell
py -3 scripts/analyze_d3d11_prof.py private/logs/opt_bench.log --markdown
```

## 2. Using the `rea` MCP Server During Xbox Porting

When the `rea` MCP server is available in your agent environment, leverage targeted read-only tools at specific porting phases:

| Porting Task | Recommended `rea` MCP Tools | How to Verify (Promote to `high`) |
|---|---|---|
| **Built Port PE Audit** | `inspect_pe_imports`, `inspect_binary_layout`, `inspect_pe_load_config` | Cross-check with `scripts/verify_port_release.py` / `objdump -p` |
| **Unknown Archive Entropy** | `inspect_byte_entropy`, `inspect_artifact` | Cross-check with `scripts/probe_containers.py` decompression |
| **Decompiling Split / Hang Functions** | `open_binary`, `analyze_function`, `procedure_pseudo_code`, `procedure_assembly`, `xrefs` | Match exact guest addresses (`sub_XXXXXXXX`) against `functions.json` & `recomp_*.c` |
| **Tracing `D3D_g_pDevice` / Kernel Callers** | `trace_call_path`, `find_xrefs_to_name`, `resolve_native_call_targets` | Verify struct offsets (e.g., `+0x2C`/`+0x30`) in raw disassembly |
| **Crash & Minidump Post-Mortem** | `inspect_recorded_crash`, `compare_functions`, `correlate_static_and_runtime` | Confirm with `SymFromAddr` / `gdb --batch` backtraces |

## 3. PowerShell Automation Pitfalls for Win32 GUI Ports (`-mwindows`)

When scripting automated smoke tests or benchmarks against a `WIN32` subsystem port on Windows:

1. **Direct invocation returns immediately:** Running `.\build\recomp\game.exe` in PowerShell does **not** wait for a `WIN32` GUI binary to exit. Always launch via `Start-Process -Wait` or `System.Diagnostics.Process` (`ProcessStartInfo` + `WaitForExit()`), or use `scripts/verify_port_release.py --test-explorer`.
2. **Avoid the `.NET` `stdout`/`stderr` Pipe Deadlock:** Calling synchronous `$p.StandardOutput.ReadToEnd()` before `$p.StandardError.ReadToEnd()` deadlocks once `stderr` fills the 4 KB pipe buffer! Always drain both streams concurrently (`ReadToEndAsync()`, `subprocess.Popen.communicate()`, or `Start-Process -RedirectStandardError`).
3. **Pass Absolute Paths for Dump & Trace Env Vars:** Because `main.c` calls `SetCurrentDirectoryA(game_dir)` for Windows Explorer compatibility, relative paths in `RECOMP_D3D11_DUMP` or `RECOMP_FRAME_TRACE` resolve inside `private/extracted/disc/` (which may be read-only!). Always pass absolute paths (`C:\...\private\logs\bench`).
4. **Flush `stdout` Before `ExitProcess(0)`:** When `stdout` is redirected to a pipe/file, C stdio switches from line-buffered to block-buffered; always call `fflush(stdout); fflush(stderr);` right before `ExitProcess(0)` in timed exit hooks so `[D3D11-PROF]` lines aren't truncated.
