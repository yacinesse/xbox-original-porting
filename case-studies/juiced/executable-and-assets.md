# *Juiced* Case Study: Executable & Asset Forensics

All findings below are **[VERIFIED]** against *Juiced* (`545100EF`) read-only disc extraction, `default.xbe` binary inspection, and Python parser validation.

## 1. XGD1 Redump Disc Extraction

- **Source Image:** `7,825,162,240` bytes (`7.2878 GiB`), SHA-256 `EE484791CD041FDDE31DDF212FECC7BDF02A9D8AC7C584B7CFF7E4FC3399B677`.
- **Partition Layout:** Standard XGD1 dual-layer DVD image:
  - Video Partition: `0x00000000` (ISO-9660 `CD001` at sector `16`).
  - Game Partition (`XDVDFS`): `0x18300000` (`405,798,912` bytes, sector `198,144`), Volume Descriptor at `0x18310000` (`MICROSOFT*XBOX*MEDIA`), Root sector `1,356,181` (`0xBDBCA800`, size `2,048` B), timestamp `2005-03-30T08:10:13.467000+00:00`.
- **Extracted Payload:** `150` directories, `1,807` files (`1.9746 GiB`).
- **Secondary Executables Present:** `dashupdate.xbe` (`58,421,248` B), `update.xbe` (`2,342,912` B) — updater XBEs, not required for core gameplay.

## 2. Executable Layout & Symbol Recovery (`default.xbe`)

- **Size & Addressing:** `3,518,464` bytes, `35` sections, Image Base `0x00010000`, Entry Point `0x001AF14A`, Kernel Thunk Table `0x002C6420` (`104+` imported Xbox kernel ordinals).
- **XDK Build:** `1.0.5849` (`XAPILIB`, `D3D8LTCG`, `D3DX8`, `XGRAPHCL`, `DSOUND`, `XACTENLT`, `XONLINES`, `XVOICE`, `VOICMAIL`).
- **Multi-Section Code Trap:** Unlike simple games that place all executable code in `.text`, `default.xbe` splits statically linked SDK/middleware libraries into separate sections:
  - Game & CRT: `.text` (`0x00012000`, `2,085,856` B — includes zlib/libjpeg/libpng)
  - Graphics/Audio/Video XDK & Middleware: `XONLINE`, `XNET`, **16 `BINK*` sections** (`BINK`, `BINK16*`, `BINK32*`, `BINK4444`, `BINK5551`, `BINKYUY2`, `BINKDATA`), `D3DX`, `DSOUND`, `WMADEC`, `XACTENG`, `XGRPH`, `D3D`, `XPP`, `DOLBY`.
  - **Lesson:** Disassembling only `.text` (`--text-only`) missed `D3D` helpers (`0x002AC9B0`, `0x002AE39B`), causing immediate recompilation/runtime failures until full-section disassembly was enabled.
- **Strings & RTTI Anchors:**
  - Embedded PDB path: `d:\Src\game\mainGame\Xbox_Release\mainGame.pdb`.
  - `XbSymbolDatabaseCLI` recovered **449 XDK 5849 symbols**, critically locating `D3D8LTCG__D3D_g_pDevice = 0x002BC378`.
  - Lifted full C output produced **12,084 → 12,268 functions** (`~1.80M` lines of C across 13 files with `--split 1000`).

## 3. Asset & Archive Container Forensics

Using read-only inspection and `scripts/probe_containers.py` patterns:

- **`.dat` Chunked-Zlib Archives (`7,632` entries verified across 8 files):** `carmesh.dat`, `carmodels.dat`, `cartextures.dat`, `mesh.dat`, `models.dat`, `scripts.dat`, `textures.dat`, `ui.dat`.
  - **Header (offset `0`):** `(uint32_le num_entries, uint32_le table_offset)`.
  - **Payload:** Entries split into 32 KiB compressed chunks (`zlib` headers `78 9C` / `78 01` / `78 DA`, indexed by `(c_off, c_sz)` pairs at `entry_off`).
  - **Footer Table (`table_offset` to EOF):** `num_entries × 20`-byte records `(name_hash, entry_off, num_chunks, comp_sz, uncomp_sz)`.
- **`.xbx` Metadata Icons (`juice*.xbx`):** Verified **`XPR0`** (Xbox Packed Resource v0) containers.
- **`.zbg` / `.zlh` Track & Scene Bundles:** Single `uint32_le uncomp_size` prefix followed by raw `zlib` stream.
- **Plain-Text Engine Data Inside `scripts.dat`:** Human-readable `[BeginCar]` Redline physics blocks (`TorqueCurveX`, `TorqueCurveY`, `ForwardGearRatios`) and `[BeginActionMap]` input tables.
- **Bink Videos (`movies/*.bik`) & XACT Banks (`audio/*.xwb`, `audio/*.xsb`):** Played natively inside the static recompilation via lifted `BINK*`, `DSOUND`, `XACTENG`, and `WMADEC` code without pre-transcoding.
