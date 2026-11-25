# Workflow 7: Validation, Regression & Documentation

**Goal:** Verify correctness, stability, standalone packaging, and repository hygiene before declaring any porting tier complete.

## Steps

1. **Automated Unit, Script & Differential Conformance Suites**
   - Verify custom analysis/extraction tools and kernel/parser unit tests pass cleanly (`py -3` / `CTest`).
   - Run **JIT / CPU conformance parity** (`RECOMP_VSH_CHECK=1` for millions of vertex runs on modified VSH JIT code, plus CPU opcode conformance vs reference interpreter).
2. **Scripted Gameplay & Control Regression (`PAD:` Replay)**
   - Execute deterministic scripted input sequences covering: boot → intro FMVs → title screen → menu navigation → level start → active movement/controls (`MPH > 0` / action response) → save/reload (`TDATA`/`UDATA`).
   - Verify keyboard bindings (genre-appropriate!) and real controller inputs (digital buttons -> `0xFF`, analog triggers/sticks, deadzones).
3. **Visual, Audio & Frame-Time Validation**
   - Inspect screenshots from `shot_*.bmp` / capture tools against `xemu` golden captures (checking HUD completeness, minimap/radar scissors, uncropped 4:3 framing, depth sorting, strip culling, and dynamic video frames).
   - Verify Bink/XMV/XACT audio plays cleanly without stalls, clipping, or A/V speed drift under both `VSync On` and `VSync Off`.
4. **Performance & Standalone Launch Verification**
   - Profile unlocked FPS (`RECOMP_PRESENT_VSYNC=0` + `RECOMP_D3D11_PROF=1`) and parse results with `py -3 scripts/analyze_d3d11_prof.py <log> --markdown`: target steady **≥ 60 FPS** heavy 3D gameplay with `miss=0` and clean `tex` timing.
   - **Automated Release & Explorer Audit:** Run `py -3 scripts/verify_port_release.py <exe> --obj-dir <build_dir> --test-explorer 12 --manifest reports/disc-manifest.json --extracted <extracted_dir> --repo .` to prove **0 non-OS DLLs** (no `libwinpthread-1.dll`), PE `.tls` present, 0 `__emutls_get_address` refs, clean launch from `C:\Windows\Temp` with `PATH` stripped to `System32`/`Windows`, unchanged `default.xbe` SHA-256, and clean repo hygiene.
   - *(PowerShell Note for `-mwindows` binaries: never call synchronous `StandardOutput.ReadToEnd()` before `StandardError.ReadToEnd()` — use `verify_port_release.py`, `Start-Process -Wait -RedirectStandardError`, or `ReadToEndAsync()`, and pass absolute paths for `RECOMP_D3D11_DUMP` because `main.c` changes CWD.)*
5. **Integrity & Legal Hygiene Check**
   - Verify `git status` and `.gitignore`: ensure **zero** `.xbe`, `.iso`, `.xpr`, `.xwb`, `.xmv`, `.bik`, `.exe`, `.bmp`, `.log`, `saves/`, screenshots of copyrighted games, or generated commercial C files are committed to Git.
   - Verify original extracted files in `private/extracted/` still match `reports/disc-manifest.json` SHA-256 hashes (checked automatically by `verify_port_release.py --manifest`), and prune excessive temporary frame dumps from `private/logs/`.
6. **Update Gate Log & Matrix**
   - Record passing evidence in `reports/gate-log.md` and `compatibility-matrix.md` with exact commands, commit hash, compiler/tool versions, and observed results (honestly listing any remaining `[UNRESOLVED]` glitches).

## Exit Gate
- [ ] All tests/checks ran **after the final edit** and passed without skipped assertions or hidden crashes.
- [ ] Explorer double-click launch verified independently of CLI CWD.
- [ ] Repo clean of all commercial binaries, assets, and temporary diagnostic log spam.
