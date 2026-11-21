# Tool Guide: Skill Python Utilities (`scripts/`)

All utilities in `scripts/` use the **Python 3.10+ standard library only** (`py -3`, zero `pip` installs needed) and open commercial game assets strictly read-only.

## 1. `xiso_inspect.py` — XISO / XGD1–3 Disc Extractor

- **When to use:** First step on any `.iso` / `.xiso` dump. Auto-detects Partition offsets (`0x0` XISO, `0x18300000` Redump XGD1, `0x0FD90000` XGD2, `0x02080000` XGD3).
- **Commands:**
  ```powershell
  py -3 scripts/xiso_inspect.py path/to/game.iso --no-hash
  py -3 scripts/xiso_inspect.py path/to/game.iso --extract private/extracted/<TITLE_ID> --manifest reports/disc-manifest.json
  ```
- **Guarantees:** Sets extracted files read-only (`0444`) and hashes payloads into a JSON manifest.

## 2. `xbe_inspect.py` — XBE Header, Library & Ordinal Inspector

- **When to use:** Immediately after extracting `default.xbe` (and secondary `.xbe`s). Decodes Retail/Debug/Chihiro XOR keys, section SHA-1 digests (`SHA1=OK/FAIL/ZERO`), XDK library builds (`D3D8` vs `D3D8LTCG`), and all `xboxkrnl.exe` ordinal imports (`1`–`378`).
- **Command:**
  ```powershell
  py -3 scripts/xbe_inspect.py private/extracted/<TITLE_ID>/default.xbe --json reports/xbe-info.json
  ```

## 3. `scan_vtables.py` — Safe `.rdata` / `.data` Vtable Seeder

- **When to use:** When static disassembly (`tools.disasm`) leaves virtual methods unlifted (`ICALL` targets missing), BEFORE blindly guessing seeds.
- **How it works:** Scans `.rdata` / `.data` aligned 32-bit words targeting executable XBE sections (`flags & 0x04` plus optional `--extra-code-sections`), groups contiguous runs (`--min-run 3`), rejects `00`/`CC`/`90` padding, and **blocks any address strictly inside an existing `functions.json` `[start, end)` range** to prevent mid-instruction splits.
- **Commands:**
  ```powershell
  # Emit xboxrecomp --seed-functions compatible JSON filtered against functions.json
  py -3 scripts/scan_vtables.py private/extracted/<TITLE_ID>/default.xbe `
      --functions Research/disasm/functions.json `
      --strict-prologue `
      -o Research/seed_functions_vtables.json

  # Emit rich vtable inspection report
  py -3 scripts/scan_vtables.py private/extracted/<TITLE_ID>/default.xbe --format detailed -o reports/vtables.json
  ```

## 4. `probe_containers.py` — Unknown Asset & Container Analyzer

- **When to use:** During Workflow 3 (Asset Extraction) to classify `.dat`, `.pak`, `.bin`, `.xbx`, `.xmv`, `.bik`, `.xwb`, `.zbg` archives without touching originals.
- **Capabilities:** Identifies Xbox magics (`XPR0/1`, `WBND`, `SDBK`, `BIKi`, `KB2`, `xobX`, `DDS `, RW/UE2/Gamebryo), probes `(uint32 count, uint32 table_offset)` footer-table archives and `[uint32 uncomp_size][zlib]` streams, measures Shannon entropy (`>7.8` = compressed/encrypted), and previews zlib/ASCII metadata.
- **Command:**
  ```powershell
  py -3 scripts/probe_containers.py private/extracted/<TITLE_ID> --recursive --extensions .dat,.xbx,.zbg,.bin --decompress-preview --json reports/asset-probe.json
  ```

## 5. `scaffold_port.py` & `init_port_db.py` — Workspace & Evidence DB

```powershell
py -3 scripts/scaffold_port.py my-port --title-id <HEX8> --name "<Title>"
py -3 scripts/init_port_db.py my-port/reports/port.db --from-xbe-json reports/xbe-info.json
```
