/*
 * kernel-override-example.c
 *
 * Illustrates the required "no silent no-ops" pattern for Original Xbox kernel
 * ordinal shims and HLE overrides:
 *  - Explicit guest 32-bit pointer types (never host void* in guest RAM)
 *  - Rate-limited diagnostic logging
 *  - Strict-mode abort on unsupported flags/paths
 *  - Clean path normalization (\Device\CdRom0\, D:, T:, U:)
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t guest_ptr_t;
typedef int32_t  ntstatus_t;

#define STATUS_SUCCESS            ((ntstatus_t)0x00000000)
#define STATUS_NOT_IMPLEMENTED    ((ntstatus_t)0xC0000002)
#define STATUS_OBJECT_NAME_NOT_FOUND ((ntstatus_t)0xC0000034)

static uint64_t g_unimplemented_api_count = 0;
static int      g_strict_mode = 1;

void xbox_report_unimplemented(uint32_t ordinal, const char* name, guest_ptr_t caller_va) {
    g_unimplemented_api_count++;
    if (g_unimplemented_api_count <= 32 || (g_unimplemented_api_count % 1000) == 0) {
        fprintf(stderr,
                "[XBOX-KERNEL][UNIMPL] ordinal=%u (%s) caller=0x%08X count=%llu\n",
                ordinal, name, caller_va, (unsigned long long)g_unimplemented_api_count);
    }
    if (g_strict_mode) {
        fprintf(stderr, "[XBOX-KERNEL][STRICT] Aborting on unimplemented API: %s\n", name);
        abort();
    }
}

/* Example: Normalize Xbox NT paths to host directories */
int xbox_normalize_path(const char* xbox_path, char* host_out, size_t host_out_sz,
                        const char* game_root, const char* save_root) {
    if (!xbox_path || !host_out || host_out_sz == 0) return -1;

    const char* rel = NULL;
    const char* base = NULL;

    if (_strnicmp(xbox_path, "\\Device\\CdRom0\\", 15) == 0) {
        base = game_root;
        rel = xbox_path + 15;
    } else if (_strnicmp(xbox_path, "D:\\", 3) == 0 || _strnicmp(xbox_path, "d:/", 3) == 0) {
        base = game_root;
        rel = xbox_path + 3;
    } else if (_strnicmp(xbox_path, "U:\\", 3) == 0 || _strnicmp(xbox_path, "T:\\", 3) == 0) {
        base = save_root;
        rel = xbox_path + 3;
    } else {
        return -1; /* Unknown or unmapped device prefix */
    }

    /* Reject path traversal */
    if (strstr(rel, "..") != NULL) return -1;

    int written = snprintf(host_out, host_out_sz, "%s/%s", base, rel);
    if (written < 0 || (size_t)written >= host_out_sz) return -1;

    for (char* p = host_out; *p; ++p) {
        if (*p == '\\') *p = '/';
    }
    return 0;
}
