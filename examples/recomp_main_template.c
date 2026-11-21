/*
 * recomp_main_template.c
 *
 * Reusable Windows host entry-point pattern for xboxrecomp-based Xbox ports.
 * Demonstrates key bring-up safeguards verified during live D3D8LTCG bring-up:
 *  1. Resolve game root relative to the executable directory (prevents Windows
 *     Explorer / shortcut crashes caused by arbitrary CWD).
 *  2. Install Win32 VEH MMIO fault trapping (xbox_VehMmioFault) so NV2A, APU,
 *     and OHCI register polls route safely without interfering with game SEH.
 *  3. Configure buffered stdio + high-resolution multimedia timer cleanly.
 *  4. Initialize OHCI USB controllers (xbox_OhciInit), APU standalone if AC97
 *     is enabled, and GPU fence mirror if needed (xbox_Nv2aMirrorFence).
 *  5. Build flat ICALL dispatch table (recomp_dispatch_init), arm watchdog on
 *     the guest thread (xbox_WatchdogStart), and launch the recompiled entry.
 */

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <xbox/xboxrecomp.h>

extern void xbox_OhciInit(void);
extern void xbox_path_init(const char *game_dir, const char *save_dir);
extern int  recomp_dispatch_init(void);
extern int  nv2a_d3d11_init_backend(void);
extern void xbe_entry_point(void);
extern MCPXAPUState *g_apu_state;

#ifndef RECOMP_FAST_TLS
extern RECOMP_TLS uint32_t g_esp;
#endif
extern ptrdiff_t g_xbox_mem_offset;

/* Customize from default.xbe (`scripts/xbe_inspect.py`) and XbSymbolDatabaseCLI */
#define GAME_ENTRY_VA       0x00010000u /* Informative banner value */
#define GAME_D3D_PDEVICE_VA 0x00000000u /* Set to D3D8LTCG__D3D_g_pDevice VA if applicable */

static LONG CALLBACK host_vectored_exception_handler(EXCEPTION_POINTERS *ep)
{
    /* Delegate trapped NV2A/APU/OHCI guest MMIO reads/writes first.
     * IMPORTANT: Do NOT swallow EXCEPTION_INT_DIVIDE_BY_ZERO or game SEH faults! */
    if (xbox_VehMmioFault(ep) == EXCEPTION_CONTINUE_EXECUTION)
        return EXCEPTION_CONTINUE_EXECUTION;

    return EXCEPTION_CONTINUE_SEARCH;
}

static void configure_game_root_cwd(void)
{
    /* Walk up from <exe_dir> looking for default.xbe or game\default.xbe so
     * double-clicking the .exe from Windows Explorer finds assets reliably. */
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(NULL, dir, sizeof(dir));
    if (len == 0 || len >= sizeof(dir))
        return;

    for (int depth = 0; depth < 6; ++depth) {
        char *slash = strrchr(dir, '\\');
        if (!slash)
            break;
        *slash = '\0';

        char probe[MAX_PATH];
        snprintf(probe, sizeof(probe), "%s\\default.xbe", dir);
        if (GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES) {
            SetCurrentDirectoryA(dir);
            return;
        }
        snprintf(probe, sizeof(probe), "%s\\game\\default.xbe", dir);
        if (GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES) {
            char game_dir[MAX_PATH];
            snprintf(game_dir, sizeof(game_dir), "%s\\game", dir);
            SetCurrentDirectoryA(game_dir);
            return;
        }
    }
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

    configure_game_root_cwd();

    /* Avoid unbuffered per-byte stderr syscalls in hot render/kernel loops */
    static char stderr_buf[65536];
    setvbuf(stderr, stderr_buf, _IOFBF, sizeof(stderr_buf));
    timeBeginPeriod(1);

    /* Safe pushbuffer/audio/input defaults (unset to disable; never set "0" on presence flags) */
    set_default_env("RECOMP_PB_EXEC", "1");
    set_default_env("RECOMP_PB_WALK", "segment"); /* Use "dma" only if NO_OPERATION IRQ is handled */
    set_default_env("RECOMP_FLIP_PACING", "0");
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
    xbox_path_init(".", NULL);
    xbox_kernel_bridge_init();
    xbox_OhciInit();

    if (GAME_D3D_PDEVICE_VA != 0u) {
        /* Mirror submitted/consumed fence offsets if title polls D3D_g_pDevice */
        xbox_Nv2aMirrorFence(GAME_D3D_PDEVICE_VA, 0x2Cu, 0x30u);
    }

    nv2a_d3d11_init_backend();

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
