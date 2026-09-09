"""Benchmark eager binary parsing and result disposal, excluding input creation and I/O."""

from __future__ import annotations

import argparse
import cProfile
from functools import partial
from dataclasses import asdict
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import pstats
import statistics
import struct
import subprocess
import sys
import time
import tracemalloc

from addressablestools import BinaryDecodeContext, DecoderRegistry, available_backends, parse_binary
from addressablestools._native import decode_registry_resources
from addressablestools.decoder import SerializedObjectDecoder
from addressablestools.models import ContentCatalogData, ResourceLocation


def pin_cpu(cpu: int) -> None:
    """Pin this benchmark process only, for comparable runs on hybrid CPUs."""
    if cpu < 0:
        raise ValueError("cpu must be non-negative")
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        if cpu >= ctypes.sizeof(ctypes.c_size_t) * 8:
            raise ValueError("cpu is outside the current Windows processor group")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        kernel32.SetProcessAffinityMask.restype = wintypes.BOOL
        if not kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), 1 << cpu):
            raise ctypes.WinError(ctypes.get_last_error())
    elif hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {cpu})
    else:
        raise ValueError("CPU affinity is not supported on this platform")


def peak_process_mib() -> float:
    """Read process high-water memory, including native allocations."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD),
                ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t),
                ("quota_peak_paged", ctypes.c_size_t), ("quota_paged", ctypes.c_size_t),
                ("quota_peak_nonpaged", ctypes.c_size_t), ("quota_nonpaged", ctypes.c_size_t),
                ("pagefile", ctypes.c_size_t), ("peak_pagefile", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.peak_working_set / 2**20

    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (2**20 if sys.platform == "darwin" else 1024)


def make_catalog(count: int, version: int = 2) -> bytes:
    """Build unique assets with shared path tails, types and bundle dependencies."""
    null = 0xFFFFFFFF
    data = bytearray(32)

    def record(fmt: str, *values: int) -> int:
        offset = len(data)
        data.extend(struct.pack(fmt, *values))
        return offset

    def string(value: str) -> int:
        raw = value.encode("ascii")
        record("<i", len(raw))
        offset = len(data)
        data.extend(raw)
        return offset

    def offsets(values: list[int]) -> int:
        record("<i", 4 * len(values))
        return record(f"<{len(values)}I", *values)

    def type_record(assembly: str, name: str) -> int:
        return record("<2I", string(assembly), string(name))

    string_type = type_record("mscorlib", "System.String")
    asset_type = type_record("UnityEngine.CoreModule", "UnityEngine.Texture2D")
    bundle_type = type_record("UnityEngine.AssetBundleModule", "UnityEngine.AssetBundle")
    provider_type = type_record("Unity.ResourceManager", "Example.Provider")
    provider = string("UnityEngine.ResourceManagement.ResourceProviders.BundledAssetProvider")
    init = record("<3I", string("provider"), provider_type, null)
    bundle_name = string("shared.bundle")
    bundle = record("<4Ii2I", bundle_name, bundle_name, provider, null, 0, null, bundle_type)
    dependencies = offsets([bundle])

    tail = null
    for part in ("Assets", "Game", "Textures", "Environment"):
        tail = record("<2I", string(part), tail)

    keys: list[int] = []
    for index in range(count):
        path = record("<2I", string(f"texture_{index}.png"), tail) | 0x40000000
        location = record("<4Ii2I", path, path, provider, dependencies, 123, null, asset_type)
        locations = offsets([location])
        for key_string, separator in ((path, ord("/")), (string(f"guid_{index:032x}"), 0)):
            payload = record("<IB", key_string, separator)
            key = record("<2I", string_type, payload)
            keys.extend((key, locations))

    keys_offset = offsets(keys)
    struct.pack_into("<ii6I", data, 0, 0, version, keys_offset, null, init, init, null, null)
    return bytes(data)


def fingerprint(catalog: ContentCatalogData) -> str:
    """Compare fields and location sharing without depending on Python's hash seed."""
    nodes: list[ResourceLocation] = []
    indices: dict[int, int] = {}

    def index(location: ResourceLocation) -> int:
        identity = id(location)
        if identity not in indices:
            indices[identity] = len(nodes)
            nodes.append(location)
        return indices[identity]

    resources = [(repr(key), [index(loc) for loc in locs]) for key, locs in catalog.resources.items()]
    records = []
    for location in nodes:
        assert location.hash_code == hash(location.internal_id) * 31 + hash(location.provider_id)
        dependencies = (
            None if location.dependencies is None else [index(loc) for loc in location.dependencies]
        )
        records.append((
            location.internal_id, location.provider_id, repr(location.dependency_key),
            dependencies, repr(location.data), location.dependency_hash_code,
            location.primary_key, repr(location.type), repr(location._data_type),
        ))
    metadata = {
        name: getattr(catalog, name)
        for name in catalog.__dataclass_fields__
        if name != "resources"
    }
    payload = json.dumps((metadata, resources, records), default=asdict, ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def make_registry(mode: str) -> DecoderRegistry | None:
    if mode == "none":
        return None
    registry = DecoderRegistry()
    if mode == "bundle":
        @registry.register(SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME)
        def decode_bundle(context: BinaryDecodeContext) -> object:
            if context.is_default:
                return None
            return context.reader.read_custom(
                context.offset,
                lambda: SerializedObjectDecoder.decode_asset_bundle_request_options_binary(
                    context.reader, context.offset,
                ),
            )
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("tests/samples/catalog.bin"))
    parser.add_argument("--synthetic-locations", type=int)
    parser.add_argument("--version", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--number", type=int, default=1)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--memory", action="store_true", help="also measure Python heap separately")
    parser.add_argument("--backend", choices=("auto", "python", "rust"), default="auto")
    parser.add_argument("--registry", choices=("none", "empty", "bundle"), default="none",
                        help="use an empty registry or a Python bundle metadata callback")
    parser.add_argument("--rss", action="store_true", help="measure process peak in a fresh worker")
    parser.add_argument("--rss-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cpu", type=int, help="pin this process to a logical CPU")
    args = parser.parse_args()
    if args.cpu is not None:
        pin_cpu(args.cpu)
    native_supported = (
        "rust" in available_backends("binary") if args.registry == "none"
        else decode_registry_resources is not None
    )
    if args.backend == "rust" and not native_supported:
        parser.error("Rust extension is not available; run: uv sync --locked")
    parse_catalog = partial(parse_binary, registry=make_registry(args.registry), backend=args.backend)
    if args.repeat < 1 or args.number < 1:
        parser.error("repeat and number must be positive")
    if args.synthetic_locations is not None and args.synthetic_locations < 1:
        parser.error("synthetic-locations must be positive")
    data = (
        make_catalog(args.synthetic_locations, args.version)
        if args.synthetic_locations is not None else args.path.read_bytes()
    )
    if args.rss_worker:
        catalog = parse_catalog(data)
        print(json.dumps({"peak_process_mib": peak_process_mib(), "keys": len(catalog.resources)}))
        return
    catalog = parse_catalog(data)
    digest = fingerprint(catalog)
    key_count = len(catalog.resources)
    version = catalog.version
    del catalog
    elapsed = []
    for _ in range(args.repeat):
        gc.collect()
        start = time.perf_counter()
        for _ in range(args.number):
            catalog = parse_catalog(data)
            del catalog
        elapsed.append((time.perf_counter() - start) / args.number)
    print(json.dumps({
        "python": platform.python_version(), "version": version,
        "backend": "rust" if args.backend != "python" and native_supported else "python",
        "cpu": args.cpu,
        "registry": args.registry,
        "bytes": len(data), "keys": key_count,
        "median_ms": statistics.median(elapsed) * 1000,
        "min_ms": min(elapsed) * 1000, "max_ms": max(elapsed) * 1000,
        "fingerprint": digest,
    }, indent=2))
    if args.profile:
        profile = cProfile.Profile()
        profile.runcall(parse_catalog, data)
        pstats.Stats(profile).strip_dirs().sort_stats("cumtime").print_stats(25)
    if args.memory:
        gc.collect()
        tracemalloc.start()
        catalog = parse_catalog(data)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del catalog
        print(json.dumps({"retained_python_mib": retained / 2**20, "peak_python_mib": peak / 2**20}))
    if args.rss:
        command = [
            sys.executable, str(Path(__file__).resolve()), str(args.path),
            "--backend", args.backend, "--registry", args.registry, "--rss-worker",
        ]
        if args.synthetic_locations is not None:
            command.extend([
                "--synthetic-locations", str(args.synthetic_locations), "--version", str(args.version),
            ])
        if args.cpu is not None:
            command.extend(["--cpu", str(args.cpu)])
        sys.stdout.flush()
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
