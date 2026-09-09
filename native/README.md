# Optional Rust accelerator

This companion package accelerates JSON and binary resource decoding for the Python package
in this repository. It uses PyO3 and returns the existing Python data classes,
including shared resource/dependency objects and provider type metadata.

## Install from this checkout

Install a Rust toolchain and the platform C/C++ linker (MSVC Build Tools on Windows),
then run this command from the repository root:

```shell
uv sync --locked --extra native
```

This builds an optimized extension and installs it into `.venv` using the local
source recorded in `uv.lock`. The ordinary parse APIs automatically use it. The base Python
package remains independently installable with setuptools and no compiler.

Without a registry, binary versions 1–3 and all built-in object types are handled
in Rust. JSON bucket,
key, location, and serialized-object fields are decoded in Rust. Top-level JSON
text and bundle option defaults/conversions retain the existing Python implementations. Since 0.3.1, ordinary numeric ID prefixes are expanded in
Rust; unusual Python integer spellings and lone surrogates retain Python handling.
Noncanonical Base64 falls back to Python's permissive decoder.
Headers, initialization metadata, and public model classes are shared across backends.

| Backend | Behavior |
| --- | --- |
| `auto` (default) | Use the installed decoder; fall back to Python when unavailable or unsupported. |
| `python` | Force the reference implementation for this call. |
| `rust` | Require native support or raise `NativeBackendUnavailableError`. |

`parse()`, `parse_json()`, `parse_binary()`, and deprecated parse functions accept
the keyword-only `backend` argument. `available_backends("json")` and
`available_backends("binary")` report installed capabilities. Selection does not
mutate global state. Native API 3 (package 0.3) supports `DecoderRegistry`, including
legacy patchers/handlers. Since 0.3.1, standard registries cache type dispatch and
decode built-in objects in Rust. `register()` and `alias()` increment a revision
that invalidates dispatch decisions, including those cached before a callback.
Custom objects still use the Python decoder with the original `BinaryDecodeContext`.
Registry subclasses and instance overrides of `_resolve`/`_get` keep the full Python
bridge. The reader and native traversal share the object cache and preserve cursor
position after scalar reads. Scalars retain Python reader operations so callback
writes to the underlying stream remain observable. Modify registries through their public methods;
direct writes to their private dictionaries bypass cache invalidation.
Registry changes during callbacks take effect on subsequent objects, and callback
exceptions propagate without retry. Custom Python functions still execute in Python;
speedup depends on how much time those functions spend decoding objects. The new
entry point is an additive API 3 capability; older API 3 extensions retain the
original registry bridge with the updated Python package.

Stream readers and non-plain-bytes buffers use Python in auto mode; forcing Rust
reports an unsupported-call error.

Native API 1 extensions remain usable for binary decoding; JSON then uses Python.
API 2 adds JSON. With either older API, registries use Python in auto mode and
raise `NativeBackendUnavailableError` when Rust is required.
Missing libraries and unknown native API versions disable acceleration in auto mode.
Malformed catalog errors propagate from the selected decoder and are not retried
through another backend.

To rebuild after Rust changes:

```shell
uv sync --locked --extra native --reinstall-package addressablestools-rust
```

To return to the Python backend:

```shell
uv sync --locked
```

Alternatively, keep the extension installed and pass `backend="python"` when comparing results.

## Build a wheel

```shell
uv build --wheel --no-sources --out-dir dist/python
uv build native --wheel --sdist --out-dir dist/native
```

Wheels use CPython's stable ABI starting at Python 3.12 and are platform-specific.
Installing a compatible prebuilt wheel does not require Rust. Building from source
requires Rust 1.88 or newer. The companion package
has its own version and build configuration; the main package's existing PyPI
publishing workflow is unchanged. No companion release has been published by this change.

The `native.yml` CI workflow builds five release wheels: manylinux2014 x86_64 and
ARM64 (glibc 2.17+), macOS Intel (10.13+) and Apple Silicon (11+), and Windows x64.
Every wheel is checked for its platform tag and stable ABI symbols, then installed
and fully tested on its own architecture under CPython 3.12 and 3.14. Source builds
are disabled during installation tests. A successful run collects the five wheels
and sdist into `addressablestools-rust-distributions`; see `PUBLISHING.md` in the
main repository for the download command and release process.

Local `uv build native` creates a host wheel. On Linux, use the manylinux CI build
for portable distribution. Alpine/musl and free-threaded Python are outside this
wheel matrix. Minimum OS tags are build targets; tests run on current CI systems.

## Verify and measure

```shell
uv run python -m pytest -q
cargo fmt --manifest-path native/Cargo.toml --check
cargo clippy --manifest-path native/Cargo.toml --lib -- -D warnings
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend python --repeat 7 --rss
uv run python benchmarks/benchmark_binary.py path/to/catalog.bin --backend rust --repeat 7 --rss
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend python --repeat 7 --rss --fingerprint
uv run python benchmarks/benchmark_json.py path/to/catalog.json --backend rust --repeat 7 --rss --fingerprint
```

Use `--cpu 0` on Windows/Linux to compare both backends on the same logical CPU.
It affects only the benchmark process. CPU migration on hybrid processors can
substantially change the observed wall time.

Native caches are per parse. Bounds checks and dynamic-string cycle detection remain
enabled. Dependency traversal uses an explicit stack, allowing deep graphs and
reporting cyclic dependencies as `BinaryReadError`. The native implementation holds
the GIL while constructing Python objects.

See [benchmark results](../benchmarks/README.md) for measured speed, memory, and
the scope of differential validation.
