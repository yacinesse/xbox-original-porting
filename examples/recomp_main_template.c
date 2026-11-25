/*
 * recomp_main_template.c
 *
 * Reusable Windows host entry-point pattern for xboxrecomp-based Xbox ports.
 * Demonstrates key bring-up safeguards verified during live D3D8LTCG bring-up:
 *  1. Verify Win64 PE TLS slot (`recomp_fast_tls_verify_init`) before guest code.
 *  2. Resolve game data & writable `saves\` directory relative to the executable
 *     path (handles Windows Explorer double-click from arbitrary CWD).
 *  3. Install Win32 VEH MMIO fault trapping (`xbox_VehMmioFault`) + host module
 *     and stack backtrace reporting without swallowing game SEH / DIV0 faults.
 *  4. Configure buffered stdio, `timeBeginPeriod(1)`, and `RECOMP_VBLANK=1`.
 *  5. Initialize OHCI USB controllers (`xbox_OhciInit`), standalone MCPX APU
 *     audio (`RECOMP_AC97_READY=1`), D3D8LTCG GPU fence mirror, D3D11 backend,
 *     and optional `RECOMP_EXIT_AFTER_SECS` automated smoke-test exit hook.
 */

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <mmsystem.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <xbox/xboxrecomp.h>
#include "recomp_fast_tls.h"

extern void xbox_OhciInit(void);
extern void xbox_path_init(const char *game_dir, const char *save_dir);
extern int  recomp_dispatch_init(void);
extern int  nv2a_d3d11_init_backend(void);
extern void xbe_entry_point(void);
extern MCPXAPUState *g_apu_state;

#ifndef RECOMP_FAST_TLS_ACTIVE
extern RECOMP_TLS uint32_t g_esp;
#endif
extern ptrdiff_t g_xbox_mem_offset;

/* Customize from default.xbe (`scripts/xbe_inspect.py`) and XbSymbolDatabaseCLI */
#define GAME_ENTRY_VA       0x00010000u /* Informative banner value */
#define GAME_D3D_PDEVICE_VA 0x00000000u /* Set to D3D8LTCG__D3D_g_pDevice VA if applicable */

static char g_game_dir[MAX_PATH] = ".";
static char g_save_dir[MAX_PATH] = "saves";

static void report_host_backtrace(void *rip)
{
    HMODULE hm = NULL;
    char mod_path[MAX_PATH] = "";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                           GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)rip, &hm) && hm) {
        GetModuleFileNameA(hm, mod_path, sizeof(mod_path));
        fprintf(stderr, "  fault module: %s + 0x%llX\n", mod_path,
                (unsigned long long)((uintptr_t)rip - (uintptr_t)hm));
    }

    void *frames[16];
    USHORT nf = CaptureStackBackTrace(0, 16, frames, NULL);
    char buf[sizeof(SYMBOL_INFO) + 256];
    SYMBOL_INFO *sym = (SYMBOL_INFO *)buf;
    for (USHORT i = 0; i < nf; ++i) {
        DWORD64 disp = 0;
        memset(buf, 0, sizeof(buf));
        sym->SizeOfStruct = sizeof(SYMBOL_INFO);
        sym->MaxNameLen = 255;
        if (SymFromAddr(GetCurrentProcess(), (DWORD64)(uintptr_t)frames[i], &disp, sym)) {
            fprintf(stderr, "    [%2u] %s+0x%llX\n", (unsigned)i, sym->Name, (unsigned long long)disp);
        } else {
            fprintf(stderr, "    [%2u] 0x%llX\n", (unsigned)i, (unsigned long long)(uintptr_t)frames[i]);
        }
    }
    fflush(stderr);
}

static LONG CALLBACK host_vectored_exception_handler(EXCEPTION_POINTERS *ep)
{
    /* Delegate trapped NV2A/APU/OHCI guest MMIO reads/writes first.
     * IMPORTANT: Never swallow EXCEPTION_INT_DIVIDE_BY_ZERO or game SEH faults! */
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        if (xbox_VehMmioFault(ep) == EXCEPTION_CONTINUE_EXECUTION)
            return EXCEPTION_CONTINUE_EXECUTION;

        /* Log unexpected non-MMIO AVs (e.g., driver SRV hazard crashes) before searching SEH */
        fprintf(stderr, "[VEH] Non-MMIO AV at %p (access=%llu addr=0x%llX)\n",
                ep->ExceptionRecord->ExceptionAddress,
                (unsigned long long)ep->ExceptionRecord->ExceptionInformation[0],
                (unsigned long long)ep->ExceptionRecord->ExceptionInformation[1]);
        report_host_backtrace(ep->ExceptionRecord->ExceptionAddress);
    }

    return EXCEPTION_CONTINUE_SEARCH;
}

static void configure_game_and_save_dirs(void)
{
    /* Walk up from <exe_dir> looking for default.xbe, game\default.xbe, or
     * private\extracted\disc\default.xbe so Explorer double-clicks always work. */
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(NULL, dir, sizeof(dir));
    if (len == 0 || len >= sizeof(dir))
        return;

    static const char *const kRelProbes[] = {
        "default.xbe",
        "game\\default.xbe",
        "private\\extracted\\disc\\default.xbe"
    };

    for (int depth = 0; depth < 6; ++depth) {
        char *slash = strrchr(dir, '\\');
        if (!slash)
            break;
        *slash = '\0';

        for (size_t i = 0; i < sizeof(kRelProbes) / sizeof(kRelProbes[0]); ++i) {
            char probe[MAX_PATH];
            snprintf(probe, sizeof(probe), "%s\\%s", dir, kRelProbes[i]);
            if (GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES) {
                char *tail = strrchr(probe, '\\');
                if (tail) *tail = '\0';
                snprintf(g_game_dir, sizeof(g_game_dir), "%s", probe);
                snprintf(g_save_dir, sizeof(g_save_dir), "%s\\saves", dir);
                CreateDirectoryA(g_save_dir, NULL);
                SetCurrentDirectoryA(g_game_dir);
                return;
            }
        }
    }
}

static DWORD WINAPI timed_exit_thread(LPVOID param)
{
    DWORD ms = (DWORD)(uintptr_t)param;
    Sleep(ms);
    fprintf(stderr, "[BOOT] Reached RECOMP_EXIT_AFTER_SECS; exiting cleanly.\n");
    fflush(stderr);
    fflush(stdout);
    ExitProcess(0);
    return 0;
}

static void set_default_env(const char *name, const char *val)
{
    if (!getenv(name)) {
        char buf[256];
        snprintf(buf, sizeof(buf), "%s=%s", name, val);
        _putenv(buf);
    }
}

static int load_file_bytes(const char *path, void **out_data, size_t *out_size)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return 0;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz <= 0) {
        fclose(f);
        return 0;
    }
    void *buf = malloc((size_t)sz);
    if (!buf || fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return 0;
    }
    fclose(f);
    *out_data = buf;
    *out_size = (size_t)sz;
    return 1;
}

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE hPrev, LPSTR cmd, int show)
{
    void *xbe_data = NULL;
    size_t xbe_size = 0;
    (void)hInst; (void)hPrev; (void)cmd; (void)show;

#ifdef RECOMP_FAST_TLS_ACTIVE
    recomp_fast_tls_verify_init();
#endif
    SymInitialize(GetCurrentProcess(), NULL, TRUE);
    configure_game_and_save_dirs();

    /* Avoid unbuffered per-byte stderr syscalls in hot render/kernel loops */
    static char stderr_buf[65536];
    setvbuf(stderr, stderr_buf, _IOFBF, sizeof(stderr_buf));
    timeBeginPeriod(1);

    /* Safe pushbuffer/audio/input defaults (unset to disable; never set "0" on presence flags) */
    set_default_env("RECOMP_PB_EXEC", "1");
    set_default_env("RECOMP_PB_WALK", "segment"); /* Use "dma" only if NO_OPERATION IRQ is handled */
    set_default_env("RECOMP_FLIP_PACING", "0");
    set_default_env("RECOMP_VBLANK", "1");
    set_default_env("RECOMP_TITLE_KEVENTS", "1");
    set_default_env("RECOMP_AC97_READY", "1");
    set_default_env("RECOMP_USB", "1");
    set_default_env("RECOMP_KEYBOARD", "1");
    set_default_env("RECOMP_STRIP_ALT_WINDING", "1");

    AddVectoredExceptionHandler(1, host_vectored_exception_handler);

    if (!load_file_bytes("default.xbe", &xbe_data, &xbe_size)) {
        MessageBoxA(NULL, "Failed to load default.xbe relative to executable path.", "Port Error", MB_ICONERROR);
        return 1;
    }
    if (!xbox_MemoryLayoutInit(xbe_data, xbe_size)) {
        MessageBoxA(NULL, "Failed to initialize Xbox memory layout.", "Port Error", MB_ICONERROR);
        free(xbe_data);
        return 1;
    }
    g_xbox_mem_offset = xbox_GetMemoryOffset();

    if (getenv("RECOMP_AC97_READY"))
        g_apu_state = mcpx_apu_init_standalone((uint8_t *)xbox_GetMemoryBase());

    xbox_kernel_init();
    xbox_path_init(g_game_dir, g_save_dir);
    xbox_kernel_bridge_init();
    xbox_OhciInit();

    if (GAME_D3D_PDEVICE_VA != 0u) {
        /* Mirror submitted/consumed fence offsets if title polls D3D_g_pDevice */
        xbox_Nv2aMirrorFence(GAME_D3D_PDEVICE_VA, 0x2Cu, 0x30u);
    }

    nv2a_d3d11_init_backend();

    if (getenv("RECOMP_EXIT_AFTER_SECS")) {
        int secs = atoi(getenv("RECOMP_EXIT_AFTER_SECS"));
        if (secs > 0)
            CreateThread(NULL, 0, timed_exit_thread, (LPVOID)(uintptr_t)((DWORD)secs * 1000u), 0, NULL);
    }

    g_esp = XBOX_STACK_TOP;
    recomp_dispatch_init();
    xbox_WatchdogStart();

    (void)GAME_ENTRY_VA;
    xbe_entry_point();

    xbox_kernel_shutdown();
    xbox_MemoryLayoutShutdown();
    free(xbe_data);
    return 0;
}
