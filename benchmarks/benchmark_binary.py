"""Benchmark eager binary parsing and result disposal, excluding input creation and I/O."""

from __future__ import annotations

import argparse
import cProfile
from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path
import platform
import pstats
import statistics
import struct
import time
import tracemalloc

from addressablestools import parse_binary
from addressablestools.models import ContentCatalogData, ResourceLocation


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("tests/samples/catalog.bin"))
    parser.add_argument("--synthetic-locations", type=int)
    parser.add_argument("--version", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--number", type=int, default=1)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--memory", action="store_true", help="also measure Python heap separately")
    args = parser.parse_args()
    if args.repeat < 1 or args.number < 1:
        parser.error("repeat and number must be positive")
    if args.synthetic_locations is not None and args.synthetic_locations < 1:
        parser.error("synthetic-locations must be positive")
    data = (
        make_catalog(args.synthetic_locations, args.version)
        if args.synthetic_locations is not None else args.path.read_bytes()
    )
    catalog = parse_binary(data)
    digest = fingerprint(catalog)
    key_count = len(catalog.resources)
    version = catalog.version
    del catalog
    elapsed = []
    for _ in range(args.repeat):
        gc.collect()
        start = time.perf_counter()
        for _ in range(args.number):
            catalog = parse_binary(data)
            del catalog
        elapsed.append((time.perf_counter() - start) / args.number)
    print(json.dumps({
        "python": platform.python_version(), "version": version,
        "bytes": len(data), "keys": key_count,
        "median_ms": statistics.median(elapsed) * 1000,
        "min_ms": min(elapsed) * 1000, "max_ms": max(elapsed) * 1000,
        "fingerprint": digest,
    }, indent=2))
    if args.profile:
        profile = cProfile.Profile()
        profile.runcall(parse_binary, data)
        pstats.Stats(profile).strip_dirs().sort_stats("cumtime").print_stats(25)
    if args.memory:
        gc.collect()
        tracemalloc.start()
        catalog = parse_binary(data)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del catalog
        print(json.dumps({"retained_python_mib": retained / 2**20, "peak_python_mib": peak / 2**20}))


if __name__ == "__main__":
    main()
