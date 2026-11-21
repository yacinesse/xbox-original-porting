# Asset Extraction & Format Forensics

This reference documents Original Xbox game asset formats, safe extraction rules, proprietary container patterns, and verified inspection/conversion commands.

## 1. Immutability & Extraction Hygiene

- **Never modify original disc dumps or extracted game files.**
- Extract to a dedicated gitignored directory (e.g., `private/extracted/<title-id>/`), set extracted files read-only (`scripts/xiso_inspect.py` sets `0444` by default), and generate a SHA-256 JSON manifest.
- Open all game assets in read-only mode (`"rb"`) in custom parsers (`scripts/probe_containers.py` is strictly read-only).
- Treat all binary headers, chunk sizes, and string tables as untrusted input—bounds-check every offset and allocation.

## 2. Common Xbox Asset & Metadata Formats

| Format / Extension | Magic / Signature | Subsystem | Purpose & Porting Notes |
|---|---|---|---|
| **XPR0 / XPR1** (`.xpr`, `.xbx`) | `XPR0` (`0x30525058`), `XPR1` | Graphics / Meta | Xbox Packed Resource: texture headers + swizzled/compressed pixels (`DXT1/3/5`, `A8R8G8B8`, `R5G6B5`, `P8`). Dashboard/save icons (`*.xbx`) also use `XPR0`! |
| **DDS** (`.dds`) | `DDS ` | Graphics | DirectDraw Surface; Xbox variants may contain swizzled layouts or non-standard FourCCs. |
| **XWB / XSB** (`.xwb`, `.xsb`) | `WBND` (`0x444E4257`), `SDBK` | Audio | XACT Wave Bank & Sound Bank: holds PCM, Xbox ADPCM (`36B`/64 samples), or WMA waves plus cue/event metadata. |
| **XMV** (`.xmv`) | `xobX` (`+0x10`) | Video | Xbox Media Video (WMV2/WMA2-derived container). Supported by FFmpeg (`xmv` demuxer). |
| **Bink** (`.bik`, `.bk2`) | `BIKi` / `KB2` | Video | RAD Game Tools Bink Video. Note: statically recompiled games with lifted `BINK*` sections + `DSOUND` + NV2A execute `.bik` natively via YUY2 pushbuffer blits! |
| **WMA / xWMA** (`.wma`, `.xwm`) | ASF GUID / `RIFF...XWMA` | Audio | Windows Media Audio; decoded by FFmpeg (`wmav1`/`wmav2`) or `vgmstream`. |
| **RenderWare** (`.rws`, `.dff`, `.txd`) | RW chunk IDs (`0x00000010` etc.) | Engine | Criterion RenderWare streams, models, and texture dictionaries. Inspect with `aap/librw`. |
| **Unreal** (`.utx`, `.ukx`, `.usx`, `.uax`) | `0x9E2A83C1` | Engine | Unreal Engine 2 packages. Inspect with `gildor2/UEViewer`. |
| **Gamebryo / NetImmerse** (`.nif`, `.kf`) | `NetImmerse` / `Gamebryo` | Engine | 3D scene graphs & animations. Inspect with `niftools/nifskope`. |

## 3. Proprietary Container Forensics & Common Patterns

Use `scripts/probe_containers.py` before writing custom C parsers:
```powershell
py -3 scripts/probe_containers.py private/extracted/<title-id> --recursive --decompress-preview --json reports/asset-probe.json
```

Look for these recurring Original Xbox archive idioms:
1. **Entropy Triage:** Shannon entropy `>= 7.8` bits/byte signals compressed (`zlib`, `LZX`, `LZSS`) or encrypted blocks; `< 6.5` usually means uncompressed structs or plain text.
2. **Footer-Table Chunked-Zlib Archives (`.dat`):**
   - Header at offset `0`: `(uint32_le num_entries, uint32_le table_offset)`.
   - Trailing index from `table_offset` to EOF (`num_entries × 16/20/24/32` bytes), storing hash/ID, payload offset, chunk count, compressed size, and uncompressed size.
   - Payloads split into fixed slices (commonly `32 KiB`) compressed independently with standard zlib headers (`78 01`, `78 5E`, `78 9C`, `78 DA`) for streaming Xbox DVD reads!
3. **Length-Prefixed Zlib Files:**
   - Single `[uint32_le uncomp_size][78 9C ...]` layout common in level/geometry bundles (`.zbg`, `.zlh`).
4. **Embedded Plain-Text Engine Scripts:**
   - Always check decompressed blocks (`--decompress-preview`) for INI/section text (`[BeginCar]`, physics curves, action maps) before reversing binary structs—many Xbox titles store gameplay tuning as plain ASCII inside compressed archives.
5. **Cross-Reference XBE Loaders:** Search `disasm/strings.json` for `.dat`/`.pak` extensions and trace xrefs to `NtCreateFile`/`NtReadFile` to confirm exact field order.

## 4. Audio & Video Conversion Commands (Verified)

Using **FFmpeg** (verified against `ffmpeg 2025-11-17` build):
```powershell
# Inspect an XMV, BIK, or WMA file
ffmpeg -hide_banner -i cutscene.xmv

# Transcode XMV/BIK cutscene to MP4 for optional local-only fallback
ffmpeg -i cutscene.xmv -c:v libx264 -crf 18 -c:a aac -b:a 192k cutscene.mp4

# Decode Xbox IMA ADPCM (.wav or extracted raw) to standard PCM WAV
ffmpeg -i voice.wav -c:a pcm_s16le voice_pcm.wav
```

Using **vgmstream** (`vgmstream-cli`):
```powershell
vgmstream-cli -m audio_bank.xwb
vgmstream-cli -S 0 -o "?s_?n.wav" audio_bank.xwb
```
*(Check FFmpeg GPL/LGPL build flags and `vgmstream` licensing before linking either library directly into a distributed binary.)*
