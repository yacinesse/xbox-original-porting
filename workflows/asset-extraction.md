# Workflow 3: Asset Extraction & Container Forensics

**Goal:** Catalog all game assets, verify source immutability, inspect known Xbox formats, and prototype bounds-checked read-only parsers for custom archives.

## Steps

1. **Verify Extracted Tree Integrity**
   - Confirm `private/extracted/<title-id>/` files are read-only (`0444`) and match `reports/disc-manifest.json` SHA-256 hashes.
2. **Run Automated Container & Entropy Triage (`scripts/probe_containers.py`)**
   - Scan extracted files without modifying them:
     ```powershell
     py -3 scripts/probe_containers.py private/extracted/<title-id> --recursive --decompress-preview --json reports/asset-probe.json
     ```
   - Group results by detected signature and Shannon entropy:
     - **Textures:** `.xpr` (`XPR0`/`XPR1`), `.xbx` icons (often `XPR0`), `.dds`, `.txd`
     - **Audio:** `.xwb` (`WBND`), `.xsb` (`SDBK`), `.wav`, `.wma`, `.ogg`
     - **Video:** `.xmv` (`xobX`), `.bik` (`BIKi`), `.bk2` (`KB2`)
     - **Archives & Scripts:** `.dat`, `.pak`, `.bin`, `.zbg`/`.zlh`, `.rws`, `.utx`, `.nif`
3. **Inspect Known Media & Decide Whether Transcoding Is Even Needed**
   - **Audio (`vgmstream` / `FFmpeg`):** Verify sample rates, channel counts, and Xbox ADPCM (`36-byte` blocks) vs WMA.
   - **Video (`Bink` vs `XMV`):** Check `.xmv` / `.bik` with `ffmpeg -hide_banner -i ...`. Remember that in a **full static recompilation**, lifted `BINK*` + `DSOUND` + NV2A code can execute `.bik` playback **natively at full speed** without offline pre-transcoding! Only prepare offline local transcoding scripts if no native/emulated playback path works.
   - **Engine Packages:** Use `aap/librw` (RenderWare), `UEViewer` (Unreal), or `NifSkope` (Gamebryo).
4. **Reverse Engineer Unknown Proprietary Containers (When Needed)**
   - Cross-reference container extensions, filenames, and error strings in `default.xbe` (`tools/disasm/strings.json` + `.xbe` xrefs to `NtCreateFile`/`NtReadFile`).
   - Check common Original Xbox container idioms caught by `probe_containers.py`:
     - **Footer-Table Chunked Zlib Archives:** `(uint32 count, uint32 table_offset)` header, chunked `0x78 0x9C / 0xDA / 0x01` payloads (`32 KiB` chunks), and fixed-stride (`16/20/24/32`-byte) footer entry records at `table_offset`.
     - **Length-Prefixed Zlib Files:** `[uint32_le uncomp_size][zlib_stream]`.
     - **Plain-Text Engine Scripts Inside Archives:** Inspect decompressed streams for ASCII sections (`[BeginCar]`, INI/CFG physics, keymaps) before assuming binary encoding.
   - Write an isolated, bounds-checked, read-only prototype parser validating decompressed byte sizes against header expectations; document known/unknown fields in `docs/format-report.md`.

## Exit Gate
- [ ] Asset inventory complete (`reports/asset-probe.json`); all formats classified.
- [ ] Source SHA-256 hashes verified unchanged.
- [ ] Custom container parsers are bounds-checked, verified against uncompressed sizes, and read-only.
