#!/usr/bin/env python3
"""Analyze [D3D11-PROF] and [GPU] profiling logs from xboxrecomp ports.

Summarizes FPS and frame-time budgets across scene complexity tiers (2D menus,
light 3D / showrooms, heavy 3D gameplay) and automatically flags common Win64 /
D3D11 NV2A bottlenecks proven in practice:
  - Texture cache hash collisions (high `miss` / `tex` ms)
  - Redundant dynamic cubemap RT face syncs (`cube` copies/frame)
  - Self-sampling RT post-processing passes (`self` snapshots/frame)
  - Guest/VSH CPU overhead dominating frame time (`frame_ms - draw_ms - flip_ms`)

Usage:
    py -3 analyze_d3d11_prof.py private/logs/opt_bench.log
    py -3 analyze_d3d11_prof.py private/logs/opt_bench.log --markdown
"""

from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

PROF_RE = re.compile(
    r"\[D3D11-PROF\]\s+"
    r"flips=(?P<flips>\d+)\s+"
    r"fps=(?P<fps>[0-9.]+)\s+"
    r"draws=(?P<draws>\d+)\s+"
    r"verts=(?P<verts>\d+)\s+"
    r"draw=(?P<draw>[0-9.]+)ms\s+"
    r"tex=(?P<tex>[0-9.]+)ms\s+"
    r"flip=(?P<flip>[0-9.]+)ms\s+"
    r"rts=(?P<rts>\d+)"
    r"(?:\s+\(hit=(?P<hit>\d+)\s+miss=(?P<miss>\d+)\s+reup=(?P<reup>\d+)\s+cube=(?P<cube>\d+)\s+self=(?P<self>\d+)\))?"
)


@dataclass(frozen=True)
class ProfSample:
    flips: int
    fps: float
    draws: int
    verts: int
    draw_ms: float
    tex_ms: float
    flip_ms: float
    rts: int
    hit: int
    miss: int
    reup: int
    cube: int
    self_copy: int

    @property
    def frame_ms(self) -> float:
        return (1000.0 / self.fps) if self.fps > 0 else 0.0

    @property
    def cpu_other_ms(self) -> float:
        return max(0.0, self.frame_ms - self.draw_ms - self.flip_ms)

    @property
    def bucket(self) -> str:
        if self.draws >= 500 and self.verts >= 40000:
            return "Heavy 3D Gameplay"
        if self.verts >= 5000 or self.rts > 4:
            return "Light 3D / Showroom"
        return "2D Menus / FMV"


def parse_log(path: Path) -> List[ProfSample]:
    samples: List[ProfSample] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        m = PROF_RE.search(line)
        if not m:
            continue
        samples.append(
            ProfSample(
                flips=int(m.group("flips")),
                fps=float(m.group("fps")),
                draws=int(m.group("draws")),
                verts=int(m.group("verts")),
                draw_ms=float(m.group("draw")),
                tex_ms=float(m.group("tex")),
                flip_ms=float(m.group("flip")),
                rts=int(m.group("rts")),
                hit=int(m.group("hit") or 0),
                miss=int(m.group("miss") or 0),
                reup=int(m.group("reup") or 0),
                cube=int(m.group("cube") or 0),
                self_copy=int(m.group("self") or 0),
            )
        )
    return samples


def summarize_bucket(items: Sequence[ProfSample]) -> Dict[str, float]:
    fps_vals = [s.fps for s in items]
    return {
        "count": float(len(items)),
        "fps_min": min(fps_vals),
        "fps_med": statistics.median(fps_vals),
        "fps_max": max(fps_vals),
        "draws_med": statistics.median(s.draws for s in items),
        "verts_med": statistics.median(s.verts for s in items),
        "draw_ms_med": statistics.median(s.draw_ms for s in items),
        "tex_ms_med": statistics.median(s.tex_ms for s in items),
        "flip_ms_med": statistics.median(s.flip_ms for s in items),
        "cpu_other_med": statistics.median(s.cpu_other_ms for s in items),
        "miss_med": statistics.median(s.miss for s in items),
        "cube_med": statistics.median(s.cube for s in items),
        "self_max": float(max(s.self_copy for s in items)),
    }


def diagnose(heavy: Sequence[ProfSample]) -> List[str]:
    notes: List[str] = []
    if not heavy:
        return ["No heavy 3D gameplay samples (>= 500 draws or >= 60k verts) found in log."]

    # Skip first transition sample when diagnosing steady state
    steady = heavy[1:] if len(heavy) > 2 else heavy
    med_fps = statistics.median(s.fps for s in steady)
    med_tex = statistics.median(s.tex_ms for s in steady)
    med_miss = statistics.median(s.miss for s in steady)
    med_cube = statistics.median(s.cube for s in steady)
    med_cpu = statistics.median(s.cpu_other_ms for s in steady)
    max_self = max(s.self_copy for s in steady)

    if med_miss >= 5 or med_tex >= 1.0:
        notes.append(
            f"[BOTTLENECK] High texture cache churn in steady 3D (median miss={med_miss:.0f}/frame, "
            f"tex={med_tex:.2f}ms). Check for aligned-address hash collisions (use multiplicative "
            f"Fibonacci hashing on offset>>6..17, expand to 512x8 ways, gate by rc.stage_program, "
            f"and canonicalize unused palette/pitch keys)."
        )
    else:
        notes.append(f"[OK] Texture cache healthy in steady 3D (median miss={med_miss:.0f}, tex={med_tex:.2f}ms).")

    if med_cube > 12:
        notes.append(
            f"[BOTTLENECK] Excessive cubemap face copies ({med_cube:.0f}/frame). Dirty-track cubemap "
            f"face RT `write_seq` so faces only sync after being rendered."
        )
    elif med_cube > 0:
        notes.append(f"[OK] Dynamic cubemap face syncs bounded ({med_cube:.0f}/frame).")

    if max_self > 0:
        notes.append(
            f"[INFO] Active RT self-sampling snapshots observed (max self={max_self}/frame) — "
            f"GPU CopyResource snapshot path is protecting radial blur / feedback passes."
        )

    if med_cpu > 8.0 and med_fps < 60.0:
        notes.append(
            f"[BOTTLENECK] Non-D3D11 CPU time dominates ({med_cpu:.1f}ms/frame, median {med_fps:.1f} FPS). "
            f"Verify RECOMP_FAST_TLS=1 (0 __emutls_get_address refs), Win64 SSE2 VSH JIT + "
            f"FastAttrStream active input mask, and disable hot stderr logging ([READ]/[GPU] draw #)."
        )
    elif med_fps >= 60.0:
        notes.append(f"[PASS] Heavy 3D gameplay meets >= 60 FPS gate (median {med_fps:.1f} FPS, cpu_other={med_cpu:.1f}ms).")

    return notes


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze [D3D11-PROF] performance logs.")
    parser.add_argument("log", type=Path, help="Path to runtime log containing [D3D11-PROF] lines")
    parser.add_argument("--markdown", action="store_true", help="Output summary as a Markdown table")
    args = parser.parse_args(argv)

    samples = parse_log(args.log)
    if not samples:
        print(f"No [D3D11-PROF] lines found in {args.log}")
        return 1

    buckets: Dict[str, List[ProfSample]] = {
        "2D Menus / FMV": [],
        "Light 3D / Showroom": [],
        "Heavy 3D Gameplay": [],
    }
    for s in samples:
        buckets[s.bucket].append(s)

    print(f"Parsed {len(samples)} [D3D11-PROF] samples from {args.log}\n")

    if args.markdown:
        print("| Scene Tier | Samples | FPS (Min / Med / Max) | Draws | Verts | draw / tex / flip (ms) | CPU Other (ms) | miss / cube |")
        print("|---|---:|---|---:|---:|---|---:|---|")
        for name, items in buckets.items():
            if not items:
                continue
            st = summarize_bucket(items)
            print(
                f"| {name} | {int(st['count'])} | "
                f"{st['fps_min']:.1f} / **{st['fps_med']:.1f}** / {st['fps_max']:.1f} | "
                f"{int(st['draws_med'])} | {int(st['verts_med']):,} | "
                f"{st['draw_ms_med']:.2f} / {st['tex_ms_med']:.2f} / {st['flip_ms_med']:.2f} | "
                f"{st['cpu_other_med']:.2f} | {int(st['miss_med'])} / {int(st['cube_med'])} |"
            )
    else:
        for name, items in buckets.items():
            if not items:
                continue
            st = summarize_bucket(items)
            print(
                f"{name:20s} ({int(st['count']):3d} samples): "
                f"FPS min={st['fps_min']:6.1f} med={st['fps_med']:6.1f} max={st['fps_max']:6.1f} | "
                f"draws={int(st['draws_med']):4d} verts={int(st['verts_med']):6d} | "
                f"draw={st['draw_ms_med']:.2f}ms tex={st['tex_ms_med']:.2f}ms flip={st['flip_ms_med']:.2f}ms "
                f"cpu={st['cpu_other_med']:.2f}ms | miss={int(st['miss_med'])} cube={int(st['cube_med'])} self_max={int(st['self_max'])}"
            )

    print("\nDiagnostics:")
    for note in diagnose(buckets["Heavy 3D Gameplay"]):
        print(" ", note)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
