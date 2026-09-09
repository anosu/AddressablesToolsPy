# Catalog parsing benchmarks

Version 1.1 bundles the Python API and Rust module in one `addressablestools`
wheel. The 0.3.x native version numbers below identify earlier development builds
of the same parsing implementation; the standalone companion is no longer needed.

Run from the repository root:

```shell
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --repeat 7
uv run python benchmarks/benchmark_binary.py --number 100
uv run python benchmarks/benchmark_binary.py --synthetic-locations 25000 --version 2
```

`--profile` adds a cProfile report. `--memory` measures the Python heap in a separate
tracemalloc run, so tracing does not affect the reported timings. Rust allocations
are not included in tracemalloc. Use `--rss` for a separate fresh-process peak
measurement that includes native allocations, the input, and Python startup, with
no tracing or fingerprint computation in that worker.

`--backend python` forces the Python path; `--backend rust` requires the installed native
extension. `--cpu 0` pins just the benchmark process to a logical CPU on Windows/Linux.

Each timed iteration fully parses the in-memory bytes and releases the catalog.
Input generation, file I/O, warmup, and result fingerprinting are excluded. Normal
garbage collection stays enabled; collection also runs before each timed batch.
Every parse uses a fresh reader and caches. These are warm-process measurements,
not Python startup or cold-disk measurements.

The fingerprint covers catalog metadata, keys, resource fields, decoded data,
type metadata, dependencies, and shared resource identity. Process-dependent hash
codes are checked against their defining formula instead of included in the digest.

## Registry dispatch and JSON prefixes (native 0.3.1)

Compared with 0.3.0 at commit `6bb00b2`, both built locally with Rust 1.97.1.
Windows x64, CPython 3.12.12, logical CPU 0, twelve measurements per version with
old/new order alternating in one process. Both native modules and both input
buffers remain loaded, so compare these paired measurements rather than absolute
times from earlier sessions. Timings include parsing and disposal; file I/O and
full-result fingerprints are outside the timed region. All fingerprints match.

| Input / registry | Native 0.3.0 | Native 0.3.1 | Time reduction |
| --- | ---: | ---: | ---: |
| Binary, none | 813 ms | 823 ms | Within measurement variation |
| Binary, empty registry | 1,595 ms | 937 ms | 41.2% |
| Binary, Python bundle decoder | 1,743 ms | 1,348 ms | 22.7% |
| JSON | 651 ms | 603 ms | 7.3% |

Separate fresh-process peak measurements fell from 218.6 to 189.1 MiB with an
empty registry and from 218.7 to 193.7 MiB with the bundle callback. JSON peak
memory stayed approximately 339 MiB. Timing differences across repeated sessions
remain sensitive to CPU clock and scheduling; these are dataset-specific results.

Standard registries now cache dispatch decisions by serialized type and registry
revision. Built-in dispatch stays native; only custom objects call the Python object
decoder. Public registry mutations invalidate decisions immediately for subsequent
objects. Subclasses and instance resolution overrides retain the original bridge.
Common JSON ID prefixes avoid Python calls; unusual integer syntax and Unicode
cases retain the reference helper. Top-level and embedded `json.loads` are unchanged.

The original registry bridge crossed into Python 222,464 times on the binary sample
even with an empty registry. The new built-in path avoids these object-decoder calls.
The JSON sample previously called the Python ID-prefix helper 111,260 times.

## Earlier DecoderRegistry integration (native 0.3.0)

Windows x64, CPython 3.12.12, logical CPU 0, seven runs on the user-provided
29,266,872-byte binary catalog (150,086 keys). Times include parsing and disposal;
peak memory comes from fresh worker processes. All six full fingerprints matched.

| Registry | Python | Rust | Speedup | Python peak | Rust peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| None | 1,787 ms | 568 ms | 3.15x | 265.8 MiB | 179.5 MiB |
| Empty | 1,775 ms | 1,104 ms | 1.61x | 265.9 MiB | 218.5 MiB |
| Python bundle decoder | 1,883 ms | 1,183 ms | 1.59x | 265.0 MiB | 218.6 MiB |

The bundle case registers a Python callback for built-in bundle metadata, preserving
its values and caching. It measures bridge overhead with real metadata; arbitrary
user callbacks can have different costs. With a registry, object dispatch remains
in Python, while Rust handles resource traversal and path decoding. Without a
registry, built-in object decoding stays native.

```shell
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend python --registry bundle --repeat 7 --rss --cpu 0
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend rust --registry bundle --repeat 7 --rss --cpu 0
```

Use `--registry empty` for an empty registry, or omit it for the ordinary fast path.
Compare backends within the same measurement session: CPU clock variation affects
absolute timings even with affinity pinned. Earlier results below are separate runs.

## Earlier integrated backends (native 0.2)

Windows x64, CPython 3.12.12, logical CPU 0, seven runs per backend. These compare
the Python and Rust implementations at that stage on the same files. Times below include
complete parsing and result disposal; process memory uses separate fresh workers.

| Input | Python | Rust | Speedup | Python peak | Rust peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Binary, 29,266,872 bytes / 150,086 keys | 2,458 ms | 552 ms | 4.45x | 266.3 MiB | 179.5 MiB |
| JSON, 60,579,906 bytes / 199,608 keys | 1,296 ms | 624 ms | 2.08x | 364.8 MiB | 339.1 MiB |

JSON parsing alone, excluding result disposal, measured 1,258 ms in Python and
596 ms in Rust. Both full-catalog fingerprints matched the reference implementation.
The JSON backend decodes Base64 directly into Python-owned buffers and releases
temporary tables before final key-map construction; binary strings reuse shared
fragments. These changes avoid paying for speed with a higher peak working set.

Backend choice uses public per-call arguments, with no process-global switches:

```shell
uv sync --locked
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend python --repeat 7 --rss --cpu 0
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend rust --repeat 7 --rss --cpu 0
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend python --repeat 7 --rss --cpu 0 --fingerprint
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend rust --repeat 7 --rss --cpu 0 --fingerprint
```

Clock speed, scheduling, and dataset structure affect the observed speedup. The
measurements below record earlier optimization stages and use their stated baselines.

## Earlier Python binary optimization

Windows x64, CPython 3.12.12; baseline commit `5120b0e` versus the Python optimization
in `7d7eb52`. The real catalog is a local user-provided file and is not distributed here.

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

## Earlier Rust prototype comparison

The [optional extension](../native/README.md) was measured against the optimized
Python backend on the same real catalog, with both processes pinned to logical
CPU 0, seven timed runs each:

| Metric | Python | Rust |
| --- | ---: | ---: |
| Median parse + disposal | 2,349 ms | 717 ms |
| Minimum / maximum | 2,294 / 2,443 ms | 550 / 735 ms |
| Fresh-process peak working set | 265.6 MiB | 183.9 MiB |

That is **3.28x faster**, with about **31% less peak process memory**. These process
memory values include the input and runtime and should not be compared with the
tracemalloc-only values in the earlier table.

The same real-catalog fingerprint matched across both backends. The version 1, 2,
and 3 synthetic fingerprints also matched the earlier Python results. Differential
tests additionally cover primitive limits/defaults, Unicode, shared metadata and
dependencies, malformed input, and deep/cyclic dependency graphs.

The earlier Python table used default scheduling. It is not directly comparable to
this pinned comparison: during native measurement the default scheduler moved the
thread between logical CPUs, with wall times ranging from roughly 0.5 to 1.7 seconds.
Use the same CPU affinity for both commands when reproducing this comparison:

```shell
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend python --repeat 7 --rss --cpu 0
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend rust --repeat 7 --rss --cpu 0
```

## Large JSON catalog

```shell
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend python --repeat 7 --rss --cpu 0
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend python --repeat 7 --profile --cpu 0
```

The JSON benchmark reports parsing and parsing-plus-disposal separately. Input
reading is excluded; `--rss` uses a fresh process, including the input and runtime.
The historical JSON measurements below explicitly use the Python backend. Native
API 2 also supports JSON; select the backend when reproducing a particular baseline.
`--fingerprint` also emits a fingerprint covering fields, metadata, and shared
resource identity; fingerprint computation is outside the timed loop.

Windows x64, CPython 3.12.12, logical CPU 0, seven timed runs, local user-provided
JSON catalog (not distributed). Initial measurements, before the Python changes below:

| Metric | Result |
| --- | ---: |
| File size | 60,579,906 bytes |
| Resource keys | 199,608 |
| Unique resource locations | 153,887 |
| Median parse | 1,707 ms |
| Minimum / maximum parse | 1,227 / 1,730 ms |
| Median parse + disposal | 1,740 ms |
| Fresh-process peak working set | 379.0 MiB |

A separate three-run phase measurement put top-level JSON text decoding at roughly
79 ms. Most time is spent decoding the embedded bucket/key/location data and
constructing the resource graph, including 27,896 bundle metadata objects. Replacing
only the top-level JSON text decoder would therefore address a small part of the
total; a native JSON-catalog path should prioritize the embedded data and resource
construction loops. The binary and JSON samples have different resource counts and
contents, so their file sizes alone do not establish a format speed comparison.

### Pure-Python JSON optimization

Both top-level and nested `json.loads()` calls retain their original implementation.
These measurements select the Python resource path. A fresh seven-run comparison
of the original JSON implementation and the optimized code used the same input,
CPython 3.12.12, logical CPU 0, and `--fingerprint --rss`:

| Metric | Before | After |
| --- | ---: | ---: |
| Median parse | 1,673 ms | 1,279 ms |
| Median parse + disposal | 1,705 ms | 1,315 ms |
| Fresh-process peak working set | 378.5 MiB | 364.4 MiB |

Parsing takes about **24% less time (1.31x faster)**. The complete fingerprints
matched for both the 60.6 MB catalog and the repository's 2.8 MB JSON sample.
The full test suite passed (199 tests), as did Mypy and Ruff.

- Bucket offsets and entry tuples use parallel lists instead of a frozen wrapper
  object for every bucket. Single-entry buckets also avoid building struct formats
  and unnecessary mapping loops.
- Resource fields are validated against cached lengths in the decoding loop.
  Valid records avoid per-field helper calls; invalid records retain field-specific
  errors, including rejection of negative required indexes.
- Internal ID prefixes are expanded once when prefixes exist, provider hashes are
  reused, and resource construction uses positional arguments.
- Built-in bundle metadata directly returns its decoded value and exact type,
  without first allocating an intermediate `ClassJsonObject`. Mutable metadata
  remains independently constructed for each resource record.
