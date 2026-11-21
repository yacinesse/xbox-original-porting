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
   - Profile unlocked FPS (`RECOMP_PRESENT_VSYNC=0` + `RECOMP_D3D11_PROF=1`): target steady **≥ 60 FPS** gameplay and fast menu responsiveness.
   - **Explorer Standalone Test:** Double-click the release `.exe` directly from Windows Explorer (outside dev terminals/repos) and confirm zero `"Failed to load default.xbe"` CWD failures or missing MinGW/DLL errors.
5. **Integrity & Legal Hygiene Check**
   - Verify `git status` and `.gitignore`: ensure **zero** `.xbe`, `.iso`, `.xpr`, `.xwb`, `.xmv`, `.bik`, screenshots of copyrighted games, or generated commercial C files are committed to Git.
   - Verify original extracted files in `private/extracted/` still match `reports/disc-manifest.json` SHA-256 hashes.
6. **Update Gate Log & Matrix**
   - Record passing evidence in `reports/gate-log.md` and `compatibility-matrix.md` with exact commands, commit hash, compiler/tool versions, and observed results (honestly listing any remaining `[UNRESOLVED]` glitches).

## Exit Gate
- [ ] All tests/checks ran **after the final edit** and passed without skipped assertions or hidden crashes.
- [ ] Explorer double-click launch verified independently of CLI CWD.
- [ ] Repo clean of all commercial binaries, assets, and temporary diagnostic log spam.
