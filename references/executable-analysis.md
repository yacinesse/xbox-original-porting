# Executable Analysis (XBE & XDVDFS)

This reference documents the Original Xbox Disc Filesystem (**XDVDFS / XISO**) and Xbox Executable (**XBE**) formats, verified against `XboxDev/pyxbe`, `antangelo/xdvdfs`, `Cxbx-Reloaded`, and retail game extractions.

## 1. XDVDFS (XISO / XGD) Disc Image Format

Xbox optical discs and disc images store game files in **XDVDFS** (Xbox DVD Filesystem):

- **Sector Size:** `2048` bytes (`0x800`).
- **Volume Descriptor Location:** Sector `32` (`0x10000` bytes from the start of the XDVDFS partition).
- **Magic Signature:** 20-byte ASCII string `MICROSOFT*XBOX*MEDIA` at offset `0x00` and repeated at offset `0x7EC` of sector 32.
- **Volume Descriptor Layout (Sector 32):**
  - `0x00..0x14`: `magic0` (`MICROSOFT*XBOX*MEDIA`)
  - `0x14..0x18`: `root_sector` (`uint32_le`)
  - `0x18..0x1C`: `root_size` (`uint32_le`, bytes)
  - `0x1C..0x24`: `filetime` (`uint64_le`, Windows FILETIME)
  - `0x7EC..0x800`: `magic1` (`MICROSOFT*XBOX*MEDIA`)

### Partition Offsets (XISO vs. Redump / Full Disc Dumps)
Depending on how the user dumped their disc, the XDVDFS partition starts at one of four known byte offsets:

| Image Type | Partition Offset (Bytes) | Hex Offset | Notes |
|---|---|---|---|
| **XISO** (trimmed/rebuilt) | `0` | `0x0` | Standard for `extract-xiso` and `xemu`-ready ISOs |
| **XGD1** (Original Xbox Redump) | `405798912` | `0x18300000` | Full dual-layer DVD dump (387 MiB video ISO-9660 `CD001` partition at `0x0`, then XDVDFS game partition) |
| **XGD2** (Xbox 360) | `265879552` | `0x0FD90000` | Included for unified tooling compatibility |
| **XGD3** (Xbox 360) | `34078720` | `0x02080000` | Included for unified tooling compatibility |

### Directory Entry Table
Directories are stored as **binary search trees** (case-insensitive UTF-8/ASCII comparison) inside contiguous sectors:
- `0x00..0x02`: `left_entry_offset` (`uint16_le`, in 4-byte units; `0` or `0xFFFF` = none)
- `0x02..0x04`: `right_entry_offset` (`uint16_le`, in 4-byte units; `0` or `0xFFFF` = none)
- `0x04..0x08`: `data_sector` (`uint32_le`)
- `0x08..0x0C`: `data_size` (`uint32_le`)
- `0x0C`: `attributes` (`uint8`: `0x01`=ReadOnly, `0x02`=Hidden, `0x04`=System, `0x10`=Directory, `0x20`=Archive, `0x80`=Normal)
- `0x0D`: `filename_length` (`uint8`)
- `0x0E..`: `filename` (not null-terminated, padded to 4-byte boundary)

Use `scripts/xiso_inspect.py` to inspect, hash, and extract any XISO/XGD1 image read-only. Remember to inspect root for secondary `.xbe` files (`dashupdate.xbe`, `update.xbe`, multiplayer `.xbe`s).

## 2. XBE (Xbox Executable) Format

An `.xbe` file is a custom PE-derived executable format with magic bytes `XBEH` (`0x48454258` LE) at offset `0x00`.

### Key Header Fields (`XbeImageHeader`)
- `0x000`: `magic` (`"XBEH"`)
- `0x004`: `signature` (256-byte RSA-2048 signature)
- `0x104`: `base_addr` (typically `0x00010000`)
- `0x108`: `headers_size`
- `0x10C`: `image_size`
- `0x110`: `image_header_size` (distinguishes Base, Extended Type 1, Extended Type 2)
- `0x114`: `timestamp` (Unix epoch)
- `0x118`: `certificate_addr`
- `0x11C`: `section_count` (commercial titles commonly contain `15`–`40+` sections)
- `0x120`: `section_headers_addr`
- `0x124`: `init_flags` (`1`=MountUtilityDrive, `2`=FormatUtilityDrive, `4`=Limit64MB, `8`=DontSetupHardDisk)
- `0x128`: `entry_addr` (**XOR-obfuscated**)
- `0x12C`: `tls_addr`
- `0x158`: `kern_thunk_addr` (**XOR-obfuscated**)
- `0x15C`: `import_dir_addr` (non-kernel imports if any)
- `0x160`: `lib_versions_count`
- `0x164`: `lib_versions_addr`

### XOR Key Decoding (Entry Point & Kernel Thunk)
Retail, Debug, and Sega Chihiro arcade XBEs use different 32-bit XOR keys:

| Build Type | Entry Point XOR Key | Kernel Thunk XOR Key |
|---|---|---|
| **Retail** | `0xA8FC57AB` | `0x5B6D40B6` |
| **Debug / Devkit** | `0x94859D4B` | `0xEFB1F152` |
| **Chihiro** | `0x40B5C16E` | `0x2290059D` |

To auto-detect build type, XOR with each pair and verify that the resulting `entry_addr` and `kern_thunk_addr` resolve inside valid XBE header/section virtual address ranges (implemented in `scripts/xbe_inspect.py`).

### Certificate (`XbeImageCertificate`)
Contains `title_id` (`uint32_le`, e.g., `0x4D530004`), `title_name` (40 × `UTF-16LE` chars), `allowed_media`, `game_region`, `disc_num`, `version`, and LAN/Signature/Alt-Signature keys.

### Section Headers, SHA-1 & Multi-Section Code Layout
Each section header (`56` bytes) includes `flags` (`0x01`=Writable, `0x02`=Preload, `0x04`=Executable), `virtual_addr`, `virtual_size`, `raw_addr`, `raw_size`, `section_name_addr`, and a 20-byte `digest`:
- **Retail XBEs:** `digest` is `SHA1(uint32_le(raw_size) + section_bytes)`.
- **Homebrew (`cxbe` / `nxdk`):** `digest` is typically all zeros (`0000...0000`, reported as `SHA1=ZERO`).
- **Multi-Section Warning (`D3D`, `DSOUND`, `BINK*`, etc.):** Commercial XBEs routinely store statically linked XDK libraries and middleware in dedicated sections (`D3D`, `D3DX`, `DSOUND`, `XACTENG`, `XGRPH`, `XPP`, `XNET`, `XONLINE`, `WMADEC`, `DOLBY`, `BINK*`, `XIPS`) — **do NOT pass `--text-only`** to disassemblers when those sections exist! Check every section name and `X` flag via `scripts/xbe_inspect.py`, and include any non-flagged code section with `--extra-sections`.

### Library Versions (`XbeLibraryVersion`)
Lists statically linked XDK/middleware libraries with 8-byte ASCII name (`XAPILIB`, `D3D8`, `D3D8LTCG`, `D3DX8`, `XGRAPHCL`, `DSOUND`, `XACTENLT`, `XONLINE`, `XONLINES`, `XNET`, `LIBCMT`, `CXBE0`, etc.) and build number (`1.0.5849`). **Always check for `D3D8LTCG` here first**—it determines whether API-level HLE or NV2A pushbuffer execution is viable.

### Kernel Import Thunk Table
A null-terminated array of `uint32_le` values at `kern_thunk_addr`. Each entry has bit 31 set (`0x80000000 | ordinal`), where `ordinal` (`1`–`378`) maps to `xboxkrnl.exe` exports (e.g., `184` = `NtAllocateVirtualMemory`, `190` = `NtCreateFile`, `165` = `MmAllocateContiguousMemory`).
