# Bundled Rust parser

This directory contains the internal Rust crate for `addressablestools._rust`.
Maturin builds it together with `src/addressablestools` and the legacy
`src/AddressablesTools.py` module into one `addressablestools` wheel. Python,
Cargo, and distribution versions are checked together; this is not an independently
published package.

## Build and install

From the repository root, with Rust 1.88+ and a platform linker installed:

```shell
uv sync --locked
uv build --wheel --sdist --out-dir dist/local
```

A compatible prebuilt wheel requires no Rust toolchain and no companion package.
To rebuild the editable installation after Rust changes:

```shell
uv sync --locked --reinstall-package addressablestools
```

## Backend behavior

| Backend | Behavior |
| --- | --- |
| `auto` | Use the bundled decoder for supported calls; otherwise use Python. |
| `python` | Use the reference implementation for this call. |
| `rust` | Require native support or raise `NativeBackendUnavailableError`. |

Binary versions 1–3, JSON embedded tables, and common ID prefixes are accelerated.
Top-level JSON decoding and bundle-option normalization retain Python semantics.
Noncanonical Base64, unusual integer prefixes, and lone surrogates use compatible
Python handling where needed. Results use the existing Python data classes.

Standard registries cache dispatch by type and registry revision. `register()` and
`alias()` invalidate cached decisions. Custom decoders keep their original
`BinaryDecodeContext`; the reader and native traversal share object caches.
Scalar reads preserve stream contents and cursor position, including callback
writes. Registry subclasses and instance method overrides use the reference object
bridge. Mutate registries through public methods: direct writes to private
dictionaries bypass revision tracking.

Stream readers and non-plain-bytes buffers retain Python handling in auto mode.
Parse errors propagate from the selected backend without retry. Caches are per parse,
bounds and cycle checks remain enabled, and iterative dependency traversal reports
cycles as `BinaryReadError`. Python object construction holds the GIL.

## Distribution verification

The reusable `native.yml` workflow builds one complete source archive, then builds
five wheels from that archive: manylinux2014 x86_64/ARM64, macOS Intel/Apple Silicon,
and Windows x64. Every wheel undergoes metadata, platform and ABI checks and is
installed offline in isolated Python 3.12 and 3.14 environments for the full tests.
The legacy module, type marker, package versions, and absence of external runtime
dependencies are verified explicitly.

See [publishing](../PUBLISHING.md) for supported platforms and release instructions,
and [benchmarks](../benchmarks/README.md) for performance measurements.

For a fresh source checkout, reference-only development tests can install just
the development group with `uv sync --locked --only-group dev`. An existing
editable build may leave a compiled `_rust` file in the source package; use
`backend="python"` to explicitly select the reference parser in that checkout.
