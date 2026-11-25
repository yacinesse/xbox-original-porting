/*
 * recomp_fast_tls.h
 *
 * Reusable Win64 TEB-slot TLS template for statically recompiled Xbox ports
 * compiled with MinGW-w64 GCC or Clang (`-DRECOMP_FAST_TLS=1`).
 *
 * Why this exists:
 *   MinGW GCC emulates `__thread` via `libgcc` `__emutls_get_address()` calls on
 *   every single register read/write across millions of lifted x86 instructions.
 *   On Windows x64, Win32 TLS slots 0..63 live inline inside the TEB at
 *   `gs:[0x1480 + slot * 8]`. Registering a PE64 `.CRT$XLB` TLS callback allocates
 *   one 16-byte-aligned `RecompFastTlsState` per host thread on attach and frees
 *   it on detach, turning every register access into a single hoisted TEB load.
 *
 * Critical Pitfalls Avoided in This Template:
 *   1. Struct members MUST carry an `r_` prefix (`r_eax`, `r_esp`, ...) because
 *      `recomp_types.h` defines `#define eax g_eax`, which would otherwise
 *      recursively macro-expand plain member names into syntax errors!
 *   2. Keep any local `static __thread` macros (e.g., `APU_TLS`, `OHCI_TLS`)
 *      OUTSIDE `#ifndef RECOMP_FAST_TLS_ACTIVE` guards.
 *   3. Reference `extern const IMAGE_TLS_DIRECTORY _tls_used;` inside
 *      `recomp_fast_tls_verify_init()` so MinGW static linking never strips the
 *      PE `.tls` DataDirectory[9] callback table.
 *
 * Usage:
 *   - Include this header from `recomp_types.h` and `xbox_memory_layout.h`.
 *   - Define `#define RECOMP_FAST_TLS_IMPLEMENTATION` in ONE runtime `.c` file
 *     (e.g., `xbox_memory_layout.c`) after `#include <windows.h>` and `<malloc.h>`.
 *   - Call `recomp_fast_tls_verify_init()` at the top of `WinMain`.
 *   - Verify 0 `__emutls_get_address` refs and DataDirectory[9] present via
 *     `scripts/verify_port_release.py`.
 */
#ifndef XBOXRECOMP_RECOMP_FAST_TLS_H
#define XBOXRECOMP_RECOMP_FAST_TLS_H

#if defined(RECOMP_FAST_TLS) && defined(_WIN64) && (defined(__GNUC__) || defined(__clang__))

#include <stdint.h>

#ifndef RECOMP_MMX_DEFINED
#define RECOMP_MMX_DEFINED
typedef union RecompMmx {
    int8_t   b[8];
    uint8_t  ub[8];
    int16_t  w[4];
    uint16_t uw[4];
    int32_t  d[2];
    uint32_t ud[2];
    uint64_t q;
} RecompMmx;
#endif

#ifndef RECOMP_XMM_DEFINED
#define RECOMP_XMM_DEFINED
typedef union RecompXmm {
    float    f[4];
    double   d[2];
    uint32_t u[4];
    int32_t  i[4];
    uint64_t q[2];
} RecompXmm;
#endif

typedef struct __attribute__((aligned(16))) RecompFastTlsState {
    uint32_t  r_eax, r_ecx, r_edx, r_esp;
    uint32_t  r_ebx, r_esi, r_edi, r_ebp;
    uint32_t  r_seh_ebp, r_fs_base, r_eflags, r_mxcsr;
    int       r_df, r_fp_top, r_fp_cmp;
    uint16_t  r_fp_control_word, r_fp_cc;
    double    r_fp_stack[8];
    RecompXmm r_xmm0, r_xmm1, r_xmm2, r_xmm3;
    RecompXmm r_xmm4, r_xmm5, r_xmm6, r_xmm7;
    RecompMmx r_mm0, r_mm1, r_mm2, r_mm3;
    RecompMmx r_mm4, r_mm5, r_mm6, r_mm7;
} RecompFastTlsState;

extern uint32_t g_recomp_teb_off;

void recomp_fast_tls_verify_init(void);

static inline __attribute__((always_inline, const))
RecompFastTlsState *recomp_fast_tls_get(void)
{
    RecompFastTlsState *p;
    uintptr_t off = (uintptr_t)g_recomp_teb_off;
    __asm__("movq %%gs:(%1), %0" : "=r"(p) : "r"(off));
    return p;
}

#define g_eax             (recomp_fast_tls_get()->r_eax)
#define g_ecx             (recomp_fast_tls_get()->r_ecx)
#define g_edx             (recomp_fast_tls_get()->r_edx)
#define g_esp             (recomp_fast_tls_get()->r_esp)
#define g_ebx             (recomp_fast_tls_get()->r_ebx)
#define g_esi             (recomp_fast_tls_get()->r_esi)
#define g_edi             (recomp_fast_tls_get()->r_edi)
#define g_ebp             (recomp_fast_tls_get()->r_ebp)
#define g_seh_ebp         (recomp_fast_tls_get()->r_seh_ebp)
#define g_fs_base         (recomp_fast_tls_get()->r_fs_base)
#define g_eflags          (recomp_fast_tls_get()->r_eflags)
#define g_mxcsr           (recomp_fast_tls_get()->r_mxcsr)
#define g_df              (recomp_fast_tls_get()->r_df)
#define g_fp_top          (recomp_fast_tls_get()->r_fp_top)
#define g_fp_cmp          (recomp_fast_tls_get()->r_fp_cmp)
#define g_fp_control_word (recomp_fast_tls_get()->r_fp_control_word)
#define g_fp_cc           (recomp_fast_tls_get()->r_fp_cc)
#define g_fp_stack        (recomp_fast_tls_get()->r_fp_stack)
#define g_xmm0            (recomp_fast_tls_get()->r_xmm0)
#define g_xmm1            (recomp_fast_tls_get()->r_xmm1)
#define g_xmm2            (recomp_fast_tls_get()->r_xmm2)
#define g_xmm3            (recomp_fast_tls_get()->r_xmm3)
#define g_xmm4            (recomp_fast_tls_get()->r_xmm4)
#define g_xmm5            (recomp_fast_tls_get()->r_xmm5)
#define g_xmm6            (recomp_fast_tls_get()->r_xmm6)
#define g_xmm7            (recomp_fast_tls_get()->r_xmm7)
#define g_mm0             (recomp_fast_tls_get()->r_mm0)
#define g_mm1             (recomp_fast_tls_get()->r_mm1)
#define g_mm2             (recomp_fast_tls_get()->r_mm2)
#define g_mm3             (recomp_fast_tls_get()->r_mm3)
#define g_mm4             (recomp_fast_tls_get()->r_mm4)
#define g_mm5             (recomp_fast_tls_get()->r_mm5)
#define g_mm6             (recomp_fast_tls_get()->r_mm6)
#define g_mm7             (recomp_fast_tls_get()->r_mm7)

#define RECOMP_FAST_TLS_ACTIVE 1

#ifdef RECOMP_FAST_TLS_IMPLEMENTATION
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#ifndef XBOX_TIB_MAIN
#define XBOX_TIB_MAIN 0x00004000u
#endif

uint32_t g_recomp_teb_off = 0;
static DWORD s_recomp_tls_slot = TLS_OUT_OF_INDEXES;

static RecompFastTlsState *recomp_fast_tls_alloc_thread(void)
{
    RecompFastTlsState *st = (RecompFastTlsState *)_aligned_malloc(sizeof(*st), 16);
    if (!st)
        return NULL;
    memset(st, 0, sizeof(*st));
    st->r_fs_base         = XBOX_TIB_MAIN;
    st->r_fp_control_word = 0x037Fu;
    st->r_mxcsr           = 0x1F80u;
    st->r_fp_cc           = 0x4000u;
    st->r_eflags          = 0x00000202u;
    return st;
}

static void NTAPI recomp_fast_tls_callback(PVOID dll, DWORD reason, PVOID reserved)
{
    (void)dll;
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        if (s_recomp_tls_slot == TLS_OUT_OF_INDEXES) {
            DWORD s = TlsAlloc();
            if (s != TLS_OUT_OF_INDEXES && s < 64u) {
                s_recomp_tls_slot = s;
                g_recomp_teb_off = 0x1480u + s * 8u;
            }
        }
        if (s_recomp_tls_slot != TLS_OUT_OF_INDEXES && !TlsGetValue(s_recomp_tls_slot)) {
            RecompFastTlsState *st = recomp_fast_tls_alloc_thread();
            if (st)
                TlsSetValue(s_recomp_tls_slot, st);
        }
    } else if (reason == DLL_THREAD_ATTACH) {
        if (s_recomp_tls_slot != TLS_OUT_OF_INDEXES && !TlsGetValue(s_recomp_tls_slot)) {
            RecompFastTlsState *st = recomp_fast_tls_alloc_thread();
            if (st)
                TlsSetValue(s_recomp_tls_slot, st);
        }
    } else if (reason == DLL_THREAD_DETACH) {
        if (s_recomp_tls_slot != TLS_OUT_OF_INDEXES) {
            RecompFastTlsState *st = (RecompFastTlsState *)TlsGetValue(s_recomp_tls_slot);
            if (st) {
                TlsSetValue(s_recomp_tls_slot, NULL);
                _aligned_free(st);
            }
        }
    }
}

__attribute__((section(".CRT$XLB"), used))
PIMAGE_TLS_CALLBACK g_recomp_fast_tls_cb = recomp_fast_tls_callback;

void recomp_fast_tls_verify_init(void)
{
    extern const IMAGE_TLS_DIRECTORY _tls_used;
    volatile const void *keep_tls = &_tls_used;
    (void)keep_tls;
    if (s_recomp_tls_slot == TLS_OUT_OF_INDEXES) {
        recomp_fast_tls_callback(NULL, DLL_PROCESS_ATTACH, NULL);
    }
    RecompFastTlsState *via_api = (RecompFastTlsState *)TlsGetValue(s_recomp_tls_slot);
    RecompFastTlsState *via_gs  = recomp_fast_tls_get();
    if (!via_api || via_api != via_gs || g_recomp_teb_off == 0) {
        fprintf(stderr, "[FAST-TLS] FATAL: TEB slot verification failed (slot=%lu off=0x%X api=%p gs=%p)\n",
                (unsigned long)s_recomp_tls_slot, g_recomp_teb_off, (void *)via_api, (void *)via_gs);
        fflush(stderr);
        abort();
    }
    fprintf(stderr, "[FAST-TLS] Win64 TEB slot %lu verified (gs:[0x%X] == %p)\n",
            (unsigned long)s_recomp_tls_slot, g_recomp_teb_off, (void *)via_gs);
    fflush(stderr);
}
#endif /* RECOMP_FAST_TLS_IMPLEMENTATION */

#else /* Non-Win64 or MSVC fallback */
static inline void recomp_fast_tls_verify_init(void) {}
#endif /* RECOMP_FAST_TLS && _WIN64 && GCC/Clang */

#endif /* XBOXRECOMP_RECOMP_FAST_TLS_H */
