# Binary parsing benchmarks

Run from the repository root:

```shell
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --repeat 7
uv run python benchmarks/benchmark_binary.py --number 100
uv run python benchmarks/benchmark_binary.py --synthetic-locations 25000 --version 2
```

`--profile` adds a cProfile report. `--memory` measures the Python heap in a separate
tracemalloc run, so tracing does not affect the reported timings.

Each timed iteration fully parses the in-memory bytes and releases the catalog.
Input generation, file I/O, warmup, and result fingerprinting are excluded. Normal
garbage collection stays enabled; collection also runs before each timed batch.
Every parse uses a fresh reader and caches. These are warm-process measurements,
not Python startup or cold-disk measurements.

The fingerprint covers catalog metadata, keys, resource fields, decoded data,
type metadata, dependencies, and shared resource identity. Process-dependent hash
codes are checked against their defining formula instead of included in the digest.

## Measured results

Windows x64, CPython 3.12.12; baseline commit `5120b0e` versus the optimized working
tree. The real catalog is a local user-provided file and is not distributed here.

| Input | Bytes | Keys | Baseline median | Optimized median | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| Real catalog, version 1 (7 runs) | 29,266,872 | 150,086 | 2,781 ms | 1,743 ms | 1.60x |
| Synthetic, version 1 (3 runs) | 3,689,370 | 50,000 | 407 ms | 198 ms | 2.05x |
| Synthetic, version 2 (3 runs) | 3,689,370 | 50,000 | 417 ms | 202 ms | 2.07x |
| Synthetic, version 3 (3 runs) | 3,689,370 | 50,000 | 413 ms | 201 ms | 2.06x |

The real catalog's traced Python heap peak fell from **218.4 MiB to 196.6 MiB**.
Retained result memory stayed approximately **102 MiB**. These figures exclude
the already-loaded input and are not total process RSS.

All four before/after fingerprints matched. The synthetic workload has unique
assets, two keys per asset, shared types, a bundle dependency, and shared linked
path tails. It exercises scaling and versions 1–3, but is not a substitute for a
broad corpus of real Unity catalogs. Small timing differences between runs are
normal; compare repeated runs on the same machine and representative files.

## Changes behind the results

- Iterate the top-level key index directly from a byte view, avoiding a large
  temporary list of offsets.
- Cache immutable type match names per reader and version. Registry aliases and
  custom decoders are still resolved on each call, preserving registry changes.
- Avoid callback and decode-context allocation on built-in/cache-hit paths.
- Cache basic strings by integer offset and reuse shared dynamic-string tails.
  Each traversal caches its first tail, avoiding construction of every suffix.
- Read buffered strings and offset arrays directly with bounds checks, avoid
  rebuilding generic type objects in hot casts, and decode bundle hashes directly
  from their serialized bytes.

The implementation remains pure Python with no runtime dependencies. Further
large improvements should be measured against a native parsing core; the remaining
work includes Python object allocation and construction of the resource graph.
