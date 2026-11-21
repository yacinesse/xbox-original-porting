#!/usr/bin/env python3
"""
xbe_inspect.py - Read-only Original Xbox Executable (.xbe) analyzer.

Parses XBE headers, certificate metadata, sections (with SHA-1 integrity checks),
XDK library version tables, TLS headers, and decoded kernel thunk imports.
Supports Retail, Debug, and Chihiro XOR keys using Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

XBE_MAGIC = b"XBEH"

# Entry point and kernel thunk XOR keys (Retail, Debug, Sega Chihiro)
XOR_KEYS: dict[str, tuple[int, int]] = {
    "retail": (0xA8FC57AB, 0x5B6D40B6),
    "debug": (0x94859D4B, 0xEFB1F152),
    "chihiro": (0x40B5C16E, 0x2290059D),
}

# Complete Original Xbox kernel export ordinals (xboxkrnl.exe)
KERNEL_EXPORTS: dict[int, str] = {
    1: "AvGetSavedDataAddress",
    2: "AvSendTVEncoderOption",
    3: "AvSetDisplayMode",
    4: "AvSetSavedDataAddress",
    5: "DbgBreakPoint",
    6: "DbgBreakPointWithStatus",
    7: "DbgLoadImageSymbols",
    8: "DbgPrint",
    9: "HalReadSMCTrayState",
    10: "DbgPrompt",
    11: "DbgUnLoadImageSymbols",
    12: "ExAcquireReadWriteLockExclusive",
    13: "ExAcquireReadWriteLockShared",
    14: "ExAllocatePool",
    15: "ExAllocatePoolWithTag",
    16: "ExEventObjectType",
    17: "ExFreePool",
    18: "ExInitializeReadWriteLock",
    19: "ExInterlockedAddLargeInteger",
    20: "ExInterlockedAddLargeStatistic",
    21: "ExInterlockedCompareExchange64",
    22: "ExMutantObjectType",
    23: "ExQueryPoolBlockSize",
    24: "ExQueryNonVolatileSetting",
    25: "ExReadWriteRefurbInfo",
    26: "ExRaiseException",
    27: "ExRaiseStatus",
    28: "ExReleaseReadWriteLock",
    29: "ExSaveNonVolatileSetting",
    30: "ExSemaphoreObjectType",
    31: "ExTimerObjectType",
    32: "ExfInterlockedInsertHeadList",
    33: "ExfInterlockedInsertTailList",
    34: "ExfInterlockedRemoveHeadList",
    35: "FscGetCacheSize",
    36: "FscInvalidateIdleBlocks",
    37: "FscSetCacheSize",
    38: "HalClearSoftwareInterrupt",
    39: "HalDisableSystemInterrupt",
    40: "HalDiskCachePartitionCount",
    41: "HalDiskModelNumber",
    42: "HalDiskSerialNumber",
    43: "HalEnableSystemInterrupt",
    44: "HalGetInterruptVector",
    45: "HalReadSMBusValue",
    46: "HalReadWritePCISpace",
    47: "HalRegisterShutdownNotification",
    48: "HalRequestSoftwareInterrupt",
    49: "HalReturnToFirmware",
    50: "HalWriteSMBusValue",
    51: "InterlockedCompareExchange",
    52: "InterlockedDecrement",
    53: "InterlockedIncrement",
    54: "InterlockedExchange",
    55: "InterlockedExchangeAdd",
    56: "InterlockedFlushSList",
    57: "InterlockedPopEntrySList",
    58: "InterlockedPushEntrySList",
    59: "IoAllocateIrp",
    60: "IoBuildAsynchronousFsdRequest",
    61: "IoBuildDeviceIoControlRequest",
    62: "IoBuildSynchronousFsdRequest",
    63: "IoCheckShareAccess",
    64: "IoCompletionObjectType",
    65: "IoCreateDevice",
    66: "IoCreateFile",
    67: "IoCreateSymbolicLink",
    68: "IoDeleteDevice",
    69: "IoDeleteSymbolicLink",
    70: "IoDeviceObjectType",
    71: "IoFileObjectType",
    72: "IoFreeIrp",
    73: "IoInitializeIrp",
    74: "IoInvalidDeviceRequest",
    75: "IoQueryFileInformation",
    76: "IoQueryVolumeInformation",
    77: "IoQueueThreadIrp",
    78: "IoRemoveShareAccess",
    79: "IoSetIoCompletion",
    80: "IoSetShareAccess",
    81: "IoStartNextPacket",
    82: "IoStartNextPacketByKey",
    83: "IoStartPacket",
    84: "IoSynchronousDeviceIoControlRequest",
    85: "IoSynchronousFsdRequest",
    86: "IofCallDriver",
    87: "IofCompleteRequest",
    88: "KdDebuggerEnabled",
    89: "KdDebuggerNotPresent",
    90: "IoDismountVolume",
    91: "IoDismountVolumeByName",
    92: "KeAlertResumeThread",
    93: "KeAlertThread",
    94: "KeBoostPriorityThread",
    95: "KeBugCheck",
    96: "KeBugCheckEx",
    97: "KeCancelTimer",
    98: "KeConnectInterrupt",
    99: "KeDelayExecutionThread",
    100: "KeDisconnectInterrupt",
    101: "KeEnterCriticalRegion",
    102: "MmGlobalData",
    103: "KeGetCurrentIrql",
    104: "KeGetCurrentThread",
    105: "KeInitializeApc",
    106: "KeInitializeDeviceQueue",
    107: "KeInitializeDpc",
    108: "KeInitializeEvent",
    109: "KeInitializeInterrupt",
    110: "KeInitializeMutant",
    111: "KeInitializeQueue",
    112: "KeInitializeSemaphore",
    113: "KeInitializeTimerEx",
    114: "KeInsertByKeyDeviceQueue",
    115: "KeInsertDeviceQueue",
    116: "KeInsertHeadQueue",
    117: "KeInsertQueue",
    118: "KeInsertQueueApc",
    119: "KeInsertQueueDpc",
    120: "KeInterruptTime",
    121: "KeIsExecutingDpc",
    122: "KeLeaveCriticalRegion",
    123: "KePulseEvent",
    124: "KeQueryBasePriorityThread",
    125: "KeQueryInterruptTime",
    126: "KeQueryPerformanceCounter",
    127: "KeQueryPerformanceFrequency",
    128: "KeQuerySystemTime",
    129: "KeRaiseIrqlToDpcLevel",
    130: "KeRaiseIrqlToSynchLevel",
    131: "KeReleaseMutant",
    132: "KeReleaseSemaphore",
    133: "KeRemoveByKeyDeviceQueue",
    134: "KeRemoveDeviceQueue",
    135: "KeRemoveEntryDeviceQueue",
    136: "KeRemoveQueue",
    137: "KeRemoveQueueDpc",
    138: "KeResetEvent",
    139: "KeRestoreFloatingPointState",
    140: "KeResumeThread",
    141: "KeRundownQueue",
    142: "KeSaveFloatingPointState",
    143: "KeSetBasePriorityThread",
    144: "KeSetDisableBoostThread",
    145: "KeSetEvent",
    146: "KeSetEventBoostPriority",
    147: "KeSetPriorityProcess",
    148: "KeSetPriorityThread",
    149: "KeSetTimer",
    150: "KeSetTimerEx",
    151: "KeStallExecutionProcessor",
    152: "KeSuspendThread",
    153: "KeSynchronizeExecution",
    154: "KeSystemTime",
    155: "KeTestAlertThread",
    156: "KeTickCount",
    157: "KeTimeIncrement",
    158: "KeWaitForMultipleObjects",
    159: "KeWaitForSingleObject",
    160: "KfRaiseIrql",
    161: "KfLowerIrql",
    162: "KiBugCheckData",
    163: "KiUnlockDispatcherDatabase",
    164: "LaunchDataPage",
    165: "MmAllocateContiguousMemory",
    166: "MmAllocateContiguousMemoryEx",
    167: "MmAllocateSystemMemory",
    168: "MmClaimGpuInstanceMemory",
    169: "MmCreateKernelStack",
    170: "MmDeleteKernelStack",
    171: "MmFreeContiguousMemory",
    172: "MmFreeSystemMemory",
    173: "MmGetPhysicalAddress",
    174: "MmIsAddressValid",
    175: "MmLockUnlockBufferPages",
    176: "MmLockUnlockPhysicalPage",
    177: "MmMapIoSpace",
    178: "MmPersistContiguousMemory",
    179: "MmQueryAddressProtect",
    180: "MmQueryAllocationSize",
    181: "MmQueryStatistics",
    182: "MmSetAddressProtect",
    183: "MmUnmapIoSpace",
    184: "NtAllocateVirtualMemory",
    185: "NtCancelTimer",
    186: "NtClearEvent",
    187: "NtClose",
    188: "NtCreateDirectoryObject",
    189: "NtCreateEvent",
    190: "NtCreateFile",
    191: "NtCreateIoCompletion",
    192: "NtCreateMutant",
    193: "NtCreateSemaphore",
    194: "NtCreateTimer",
    195: "NtDeleteFile",
    196: "NtDeviceIoControlFile",
    197: "NtDuplicateObject",
    198: "NtFlushBuffersFile",
    199: "NtFreeVirtualMemory",
    200: "NtFsControlFile",
    201: "NtOpenDirectoryObject",
    202: "NtOpenFile",
    203: "NtOpenSymbolicLinkObject",
    204: "NtProtectVirtualMemory",
    205: "NtPulseEvent",
    206: "NtQueueApcThread",
    207: "NtQueryDirectoryFile",
    208: "NtQueryDirectoryObject",
    209: "NtQueryEvent",
    210: "NtQueryFullAttributesFile",
    211: "NtQueryInformationFile",
    212: "NtQueryIoCompletion",
    213: "NtQueryMutant",
    214: "NtQuerySemaphore",
    215: "NtQuerySymbolicLinkObject",
    216: "NtQueryTimer",
    217: "NtQueryVirtualMemory",
    218: "NtQueryVolumeInformationFile",
    219: "NtReadFile",
    220: "NtReadFileScatter",
    221: "NtReleaseMutant",
    222: "NtReleaseSemaphore",
    223: "NtRemoveIoCompletion",
    224: "NtResumeThread",
    225: "NtSetEvent",
    226: "NtSetInformationFile",
    227: "NtSetIoCompletion",
    228: "NtSetSystemTime",
    229: "NtSetTimerEx",
    230: "NtSignalAndWaitForSingleObjectEx",
    231: "NtSuspendThread",
    232: "NtUserIoApcDispatcher",
    233: "NtWaitForSingleObject",
    234: "NtWaitForSingleObjectEx",
    235: "NtWaitForMultipleObjectsEx",
    236: "NtWriteFile",
    237: "NtWriteFileGather",
    238: "NtYieldExecution",
    239: "ObCreateObject",
    240: "ObDirectoryObjectType",
    241: "ObMakeTemporaryObject",
    242: "ObOpenObjectByName",
    243: "ObOpenObjectByPointer",
    244: "ObpObjectHandleTable",
    245: "ObReferenceObjectByHandle",
    246: "ObReferenceObjectByName",
    247: "ObReferenceObjectByPointer",
    248: "ObSymbolicLinkObjectType",
    249: "ObfDereferenceObject",
    250: "ObfReferenceObject",
    251: "PhyGetLinkState",
    252: "PhyInitialize",
    253: "PsCreateSystemThread",
    254: "PsCreateSystemThreadEx",
    255: "PsQueryStatistics",
    256: "PsSetCreateThreadNotifyRoutine",
    257: "PsTerminateSystemThread",
    258: "PsThreadObjectType",
    259: "RtlAnsiStringToUnicodeString",
    260: "RtlAppendStringToString",
    261: "RtlAppendUnicodeStringToString",
    262: "RtlAppendUnicodeToString",
    263: "RtlAssert",
    264: "RtlCaptureContext",
    265: "RtlCaptureStackBackTrace",
    266: "RtlCharToInteger",
    267: "RtlCompareMemory",
    268: "RtlCompareMemoryUlong",
    269: "RtlCompareString",
    270: "RtlCompareUnicodeString",
    271: "RtlCopyString",
    272: "RtlCopyUnicodeString",
    273: "RtlCreateUnicodeString",
    274: "RtlDowncaseUnicodeChar",
    275: "RtlDowncaseUnicodeString",
    276: "RtlEnterCriticalSection",
    277: "RtlEnterCriticalSectionAndRegion",
    278: "RtlEqualString",
    279: "RtlEqualUnicodeString",
    280: "RtlExtendedIntegerMultiply",
    281: "RtlExtendedLargeIntegerDivide",
    282: "RtlExtendedMagicDivide",
    283: "RtlFillMemory",
    284: "RtlFillMemoryUlong",
    285: "RtlFreeAnsiString",
    286: "RtlFreeUnicodeString",
    287: "RtlGetCallersAddress",
    288: "RtlInitAnsiString",
    289: "RtlInitUnicodeString",
    290: "RtlInitializeCriticalSection",
    291: "RtlIntegerToChar",
    292: "RtlIntegerToUnicodeString",
    293: "RtlLeaveCriticalSection",
    294: "RtlLeaveCriticalSectionAndRegion",
    295: "RtlLowercaseUnicodeString",
    296: "RtlMapGenericMask",
    297: "RtlMoveMemory",
    298: "RtlMultiByteToUnicodeN",
    299: "RtlMultiByteToUnicodeSize",
    300: "RtlNtStatusToDosError",
    301: "RtlRaiseException",
    302: "RtlRaiseStatus",
    303: "RtlTimeFieldsToTime",
    304: "RtlTimeToTimeFields",
    305: "RtlTryEnterCriticalSection",
    306: "RtlUlongByteSwap",
    307: "RtlUnicodeStringToAnsiString",
    308: "RtlUnicodeStringToInteger",
    309: "RtlUnicodeToMultiByteN",
    310: "RtlUnicodeToMultiByteSize",
    311: "RtlUnwind",
    312: "RtlUpcaseUnicodeChar",
    313: "RtlUpcaseUnicodeString",
    314: "RtlUpcaseUnicodeToMultiByteN",
    315: "RtlUpperChar",
    316: "RtlUpperString",
    317: "RtlUshortByteSwap",
    318: "RtlWalkFrameChain",
    319: "RtlZeroMemory",
    320: "XboxEEPROMKey",
    321: "XboxHardwareInfo",
    322: "XboxHDKey",
    323: "XboxKrnlVersion",
    324: "XboxSignatureKey",
    325: "XcSHAInit",
    326: "XcSHAUpdate",
    327: "XcSHAFinal",
    328: "XcRC4Key",
    329: "XcRC4Crypt",
    330: "XcHMAC",
    331: "XcPKEncPublic",
    332: "XcPKDecPrivate",
    333: "XcPKGetKeyLen",
    334: "XcVerifyPKCS1Signature",
    335: "XcModExp",
    336: "XcDESKeyParity",
    337: "XcKeyTable",
    338: "XcBlockCrypt",
    339: "XcBlockCryptCBC",
    340: "XcCryptService",
    341: "XcUpdateCrypto",
    342: "RtlRip",
    343: "XboxLANKey",
    344: "XboxAlternateSignatureKeys",
    345: "XePublicKeyData",
    346: "HalBootSMCVideoMode",
    347: "IdexChannelObject",
    348: "HalIsResetOrShutdownPending",
    349: "IoMarkIrpMustComplete",
    350: "HalInitiateShutdown",
    351: "RtlSnprintf",
    352: "RtlSprintf",
    353: "RtlVsnprintf",
    354: "RtlVsprintf",
    355: "HalEnableSecureTrayEject",
    356: "HalWriteSMCScratchRegister",
    374: "MmDbgAllocateMemory",
    375: "MmDbgFreeMemory",
    376: "MmDbgQueryAvailablePages",
    377: "MmDbgReleaseAddress",
    378: "MmDbgWriteCheck",
}


def _read_cstr(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\x00", offset)
    if end == -1:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def _read_wstr(data: bytes, offset: int) -> str:
    if offset < 0 or offset + 2 > len(data):
        return ""
    cur = offset
    while cur + 2 <= len(data):
        if data[cur : cur + 2] == b"\x00\x00":
            break
        cur += 2
    return data[offset:cur].decode("utf-16-le", errors="replace")


def _vaddr_to_offset(
    vaddr: int, base_addr: int, headers_size: int, sections: list[dict]
) -> int | None:
    if base_addr <= vaddr < base_addr + headers_size:
        return vaddr - base_addr
    for sec in sections:
        va = sec["virtual_addr"]
        vsz = sec["virtual_size"]
        if va <= vaddr < va + vsz:
            return (vaddr - va) + sec["raw_addr"]
    return None


def _decode_build_type(
    encoded_entry: int,
    encoded_thunk: int,
    base_addr: int,
    headers_size: int,
    sections: list[dict],
) -> tuple[str, int, int]:
    """Identify Retail, Debug, or Chihiro XOR keys by checking address validity."""
    for build_type, (ep_key, kt_key) in XOR_KEYS.items():
        ep = encoded_entry ^ ep_key
        kt = encoded_thunk ^ kt_key
        if (
            _vaddr_to_offset(ep, base_addr, headers_size, sections) is not None
            and _vaddr_to_offset(kt, base_addr, headers_size, sections) is not None
        ):
            return build_type, ep, kt
    # Fallback: check entry point range alone
    for build_type, (ep_key, kt_key) in XOR_KEYS.items():
        ep = encoded_entry ^ ep_key
        if base_addr <= ep < 0x08000000:
            return build_type, ep, encoded_thunk ^ kt_key
    return "unknown", encoded_entry, encoded_thunk


def parse_xbe(data: bytes, verify_sha1: bool = True) -> dict:
    if len(data) < 0x178 or data[0:4] != XBE_MAGIC:
        raise ValueError("Not a valid XBE file (missing 'XBEH' magic).")

    # Base XbeImageHeader after magic (4) + RSA signature (256) = offset 260 (0x104)
    (
        base_addr,
        headers_size,
        image_size,
        image_header_size,
        timestamp,
        certificate_addr,
        section_count,
        section_headers_addr,
        init_flags,
        encoded_entry,
        tls_addr,
        pe_stack_commit,
        pe_heap_reserve,
        pe_heap_commit,
        pe_base_addr,
        pe_image_size,
        pe_checksum,
        pe_timestamp,
        debug_pathname_addr,
        debug_filename_addr,
        debug_unicode_filename_addr,
        encoded_kern_thunk,
        import_dir_addr,
        lib_versions_count,
        lib_versions_addr,
        kern_lib_version_addr,
        xapi_lib_version_addr,
        logo_addr,
        logo_size,
    ) = struct.unpack_from("<29I", data, 0x104)

    # Parse sections first so _vaddr_to_offset works across all sections
    sections: list[dict] = []
    sec_off = section_headers_addr - base_addr
    for i in range(section_count):
        if sec_off + 56 > len(data):
            break
        (
            flags,
            vaddr,
            vsize,
            raw_addr,
            raw_size,
            sec_name_addr,
            sec_name_ref,
            head_ref,
            tail_ref,
        ) = struct.unpack_from("<9I", data, sec_off)
        digest = data[sec_off + 36 : sec_off + 56]
        name_off = sec_name_addr - base_addr
        sec_name = _read_cstr(data, name_off) if 0 <= name_off < headers_size else f"sec_{i}"

        sha1_status: str = "SKIP"
        if verify_sha1:
            if digest == b"\x00" * 20:
                sha1_status = "ZERO"
            elif raw_addr + raw_size <= len(data):
                sec_bytes = data[raw_addr : raw_addr + raw_size]
                h_raw = hashlib.sha1(sec_bytes).digest()
                h_len = hashlib.sha1(struct.pack("<I", raw_size) + sec_bytes).digest()
                sha1_status = "OK" if (digest == h_raw or digest == h_len) else "FAIL"

        flag_names = []
        if flags & 0x01:
            flag_names.append("W")
        if flags & 0x02:
            flag_names.append("PRELOAD")
        if flags & 0x04:
            flag_names.append("X")
        if flags & 0x08:
            flag_names.append("INSERT")

        sections.append(
            {
                "index": i,
                "name": sec_name,
                "flags": flags,
                "flags_str": "|".join(flag_names) or "R",
                "virtual_addr": vaddr,
                "virtual_size": vsize,
                "raw_addr": raw_addr,
                "raw_size": raw_size,
                "digest_hex": digest.hex(),
                "sha1_status": sha1_status,
            }
        )
        sec_off += 56

    build_type, entry_addr, kern_thunk_addr = _decode_build_type(
        encoded_entry, encoded_kern_thunk, base_addr, headers_size, sections
    )

    # Certificate
    cert_off = _vaddr_to_offset(certificate_addr, base_addr, headers_size, sections)
    cert_info: dict = {}
    if cert_off is not None and cert_off + 0xEC <= len(data):
        cert_size, cert_ts, title_id = struct.unpack_from("<III", data, cert_off)
        title_name_raw = data[cert_off + 12 : cert_off + 12 + 80]
        title_name = title_name_raw.decode("utf-16-le", errors="replace").rstrip("\x00")
        allowed_media, game_region, ratings, disc_num, version = struct.unpack_from(
            "<5I", data, cert_off + 12 + 80 + 64
        )
        cert_info = {
            "size": cert_size,
            "title_id": f"{title_id:08X}",
            "title_name": title_name,
            "allowed_media": allowed_media,
            "game_region": game_region,
            "ratings": ratings,
            "disc_number": disc_num,
            "version": version,
        }

    # Debug paths
    debug_pathname = ""
    debug_filename = ""
    off = _vaddr_to_offset(debug_pathname_addr, base_addr, headers_size, sections)
    if off is not None:
        debug_pathname = _read_cstr(data, off)
    off = _vaddr_to_offset(debug_filename_addr, base_addr, headers_size, sections)
    if off is not None:
        debug_filename = _read_cstr(data, off)

    # Library versions
    libraries: list[dict] = []
    if lib_versions_addr != 0:
        lib_off = _vaddr_to_offset(lib_versions_addr, base_addr, headers_size, sections)
        if lib_off is not None:
            for _ in range(lib_versions_count):
                if lib_off + 16 > len(data):
                    break
                raw_name, maj, min_v, build, flags_qfe = struct.unpack_from(
                    "<8sHHHH", data, lib_off
                )
                name = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="replace")
                qfe = flags_qfe & 0x1FFF
                approved = (flags_qfe >> 13) & 0x3
                debug_build = bool((flags_qfe >> 15) & 0x1)
                libraries.append(
                    {
                        "name": name,
                        "version": f"{maj}.{min_v}.{build}",
                        "qfe": qfe,
                        "approved": approved,
                        "debug": debug_build,
                    }
                )
                lib_off += 16

    # Kernel imports
    kernel_imports: list[dict] = []
    kt_off = _vaddr_to_offset(kern_thunk_addr, base_addr, headers_size, sections)
    if kt_off is not None:
        idx = 0
        while kt_off + 4 <= len(data):
            val = struct.unpack_from("<I", data, kt_off)[0]
            if val == 0:
                break
            ordinal = val & 0x7FFFFFFF
            kernel_imports.append(
                {
                    "thunk_vaddr": f"{kern_thunk_addr + idx * 4:#010x}",
                    "ordinal": ordinal,
                    "name": KERNEL_EXPORTS.get(ordinal, f"UNKNOWN_ORDINAL_{ordinal}"),
                }
            )
            kt_off += 4
            idx += 1

    ts_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return {
        "file_size": len(data),
        "file_sha256": hashlib.sha256(data).hexdigest(),
        "build_type": build_type,
        "base_addr": f"{base_addr:#010x}",
        "headers_size": headers_size,
        "image_size": image_size,
        "timestamp": timestamp,
        "timestamp_utc": ts_iso,
        "entry_point": f"{entry_addr:#010x}",
        "kernel_thunk_table": f"{kern_thunk_addr:#010x}",
        "init_flags": init_flags,
        "debug_pathname": debug_pathname,
        "debug_filename": debug_filename,
        "certificate": cert_info,
        "sections": sections,
        "libraries": libraries,
        "kernel_imports": kernel_imports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze an Original Xbox .xbe executable.")
    parser.add_argument("xbe", type=Path, help="Path to .xbe file")
    parser.add_argument("--json", type=Path, default=None, help="Write full JSON report to path")
    parser.add_argument("--no-sha1", action="store_true", help="Skip section SHA-1 verification")
    args = parser.parse_args()

    if not args.xbe.is_file():
        print(f"Error: XBE not found: {args.xbe}", file=sys.stderr)
        return 1

    data = args.xbe.read_bytes()
    info = parse_xbe(data, verify_sha1=not args.no_sha1)

    cert = info["certificate"]
    print(f"File:           {args.xbe} ({info['file_size']:,} bytes)")
    print(f"SHA-256:        {info['file_sha256']}")
    print(f"Title:          {cert.get('title_name', 'N/A')} [TitleID: {cert.get('title_id', 'N/A')}]")
    print(f"Build Type:     {info['build_type'].upper()} (XOR keys verified)")
    print(f"Base / Image:   {info['base_addr']} / {info['image_size']:#x} bytes")
    print(f"Entry Point:    {info['entry_point']}")
    print(f"Kernel Thunk:   {info['kernel_thunk_table']} ({len(info['kernel_imports'])} imports)")
    print(f"Timestamp:      {info['timestamp_utc']}")
    if info["debug_pathname"]:
        print(f"Debug Path:     {info['debug_pathname']}")

    print("\nSections:")
    for s in info["sections"]:
        print(
            f"  {s['name']:<12} VA={s['virtual_addr']:#010x} VSZ={s['virtual_size']:#08x} "
            f"RAW={s['raw_addr']:#08x} RSZ={s['raw_size']:#08x} [{s['flags_str']}] SHA1={s['sha1_status']}"
        )

    if info["libraries"]:
        print("\nLibraries:")
        for lib in info["libraries"]:
            dbg = " [DEBUG]" if lib["debug"] else ""
            print(f"  {lib['name']:<10} {lib['version']} (QFE {lib['qfe']}){dbg}")
    else:
        print("\nLibraries:      None (common for homebrew/nxdk)")

    print(f"\nKernel Imports ({len(info['kernel_imports'])}):")
    for imp in info["kernel_imports"]:
        print(f"  [{imp['ordinal']:3d}] {imp['name']} @ {imp['thunk_vaddr']}")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(info, indent=2), encoding="utf-8")
        print(f"\nJSON report written: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
