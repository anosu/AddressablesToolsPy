"""Measure eager JSON catalog parsing, with file I/O outside the timed loop."""

from __future__ import annotations

import argparse
import cProfile
from functools import partial
import gc
import json
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import time

from benchmark_binary import fingerprint, peak_process_mib, pin_cpu

from addressablestools import available_backends, parse_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--backend", choices=("auto", "python", "rust"), default="auto")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--rss", action="store_true")
    parser.add_argument("--fingerprint", action="store_true", help="emit a result fingerprint to compare")
    parser.add_argument("--rss-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.backend == "rust" and "rust" not in available_backends("json"):
        parser.error("Rust JSON extension is not available; run: uv sync --extra native")
    parse_catalog = partial(parse_json, backend=args.backend)
    if args.repeat < 1:
        parser.error("repeat must be positive")
    if args.cpu is not None:
        pin_cpu(args.cpu)
    data = args.path.read_text(encoding="utf-8-sig")
    catalog = parse_catalog(data)
    if args.rss_worker:
        print(json.dumps({"peak_process_mib": peak_process_mib(), "keys": len(catalog.resources)}))
        return
    key_count = len(catalog.resources)
    location_count = len({id(loc) for locations in catalog.resources.values() for loc in locations})
    digest = fingerprint(catalog) if args.fingerprint else None
    del catalog
    parse_times = []
    total_times = []
    for _ in range(args.repeat):
        gc.collect()
        start = time.perf_counter()
        catalog = parse_catalog(data)
        parse_times.append(time.perf_counter() - start)
        del catalog
        total_times.append(time.perf_counter() - start)
    print(json.dumps({
        "python": platform.python_version(), "cpu": args.cpu,
        "backend": "rust" if args.backend != "python" and "rust" in available_backends("json") else "python",
        "bytes": args.path.stat().st_size, "keys": key_count, "locations": location_count,
        "median_parse_ms": statistics.median(parse_times) * 1000,
        "min_parse_ms": min(parse_times) * 1000, "max_parse_ms": max(parse_times) * 1000,
        "median_parse_and_disposal_ms": statistics.median(total_times) * 1000,
        "fingerprint": digest,
    }, indent=2), flush=True)
    if args.profile:
        profile = cProfile.Profile()
        profile.runcall(parse_catalog, data)
        pstats.Stats(profile).strip_dirs().sort_stats("cumtime").print_stats(25)
    if args.rss:
        command = [
            sys.executable, str(Path(__file__).resolve()), str(args.path),
            "--backend", args.backend, "--rss-worker",
        ]
        if args.cpu is not None:
            command.extend(["--cpu", str(args.cpu)])
        sys.stdout.flush()
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
