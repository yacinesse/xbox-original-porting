/*
 * recomp_manual_wrapper_example.c
 *
 * Demonstrates durable manual overrides for static recompilation using
 * xboxrecomp's `--exclude-manual` workflow:
 *  - Place durable fixes here (not directly in generated `recomp_*.c`), so
 *    re-running tools.recomp never overwrites your fixes.
 *  - `recomp_lookup_manual(va)` intercepts indirect calls (ICALL) and table lookups.
 *  - Combine `--exclude-manual path/to/recomp_manual.c` when running tools.recomp.
 */

#include <stdint.h>
#include <stdio.h>

/* Included from xboxrecomp runtime/generated headers in a real project:
 * #include "recomp_types.h"
 * #include "xbox_memory_layout.h" */

extern void sub_00100000_gen(void); /* Generated fallback if wrapped (see tools/recomp --exclude-manual) */

typedef void (*recomp_func_t)(void);

/*
 * Pattern 1: Merging a mid-instruction function split.
 *
 * Symptom: tools.disasm split Function A cleanly around an internal branch target
 * or tail-call at Address B. Calling A falls into a generated stub or emits a
 * mismatched stack prologue (`sub esp, ...` twice / callee-save clobber).
 *
 * Fix: Define the complete merged `sub_XXXXXXXX(void)` once here with full
 * basic blocks `loc_XXXXXXXX:` and compile with `--exclude-manual`.
 */
void sub_00100000(void)
{
    /* Example merged implementation replacing split generated blocks.
     * Keep prologue/epilogue stack depth (`esp += N`) matching the guest ABI! */
    printf("[MANUAL] Executing merged override for 0x00100000\n");
}

/*
 * Pattern 2: Bounded hardware MMIO poll wrapper.
 *
 * Symptom: Title/XDK polls an MMIO bit in a tight loop (`while (MEM8(mmio) & mask)`),
 * or caches the read byte before looping, hanging at 0.00 FPS if the emulated device
 * does not clear the bit synchronously on that same CPU thread.
 *
 * Fix: Override the polling routine (e.g., MCPX APU doorbell wait at 0xFEC0010B)
 * with a bounded loop that re-reads volatile guest MMIO memory and breaks cleanly.
 */
void sub_00200000_mmio_poll_safe(void)
{
    const uint32_t mmio_status_va = 0xFEC0010Bu;
    volatile uint8_t *status_ptr = (volatile uint8_t *)(uintptr_t)mmio_status_va; /* map via guest base in real port */

    for (int spin = 0; spin < 1000; ++spin) {
        uint8_t val = *status_ptr;
        if ((val & 0x02u) == 0u)
            break;
    }
}

recomp_func_t recomp_lookup_manual(uint32_t xbox_va)
{
    switch (xbox_va) {
    case 0x00100000u: return sub_00100000;
    case 0x00200000u: return sub_00200000_mmio_poll_safe;
    default:          return NULL;
    }
}
