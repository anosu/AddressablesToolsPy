# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-10

### Added

- Rust acceleration for binary and JSON resource decoding, bundled with the Python
  API in a single platform wheel. No separate accelerator package is required.
- Per-call `backend="auto"`, `"python"`, or `"rust"` selection, format-specific
  `available_backends()`, and `NativeBackendUnavailableError` for strict selection.
- Differential tests, malformed-input coverage, isolated wheel verification, and
  Python 3.12/3.14 native CI on Windows, Linux, and macOS.
- `DecoderRegistry` support through shared-cache
  resource traversal and Python object dispatch, including aliases, custom keys,
  built-in overrides, nested decoding, and live registry changes.
- Portable native wheel builds for Linux x86_64/ARM64 (manylinux2014), macOS
  Intel/Apple Silicon, and Windows x64, with platform/ABI audits and complete tests
  against installed wheels on Python 3.12 and 3.14.

### Changed

- Maturin now builds Python and Rust together at version 1.1.0. The `native` extra
  remains a compatibility alias; `backend="python"` selects the reference parser.
- Built-in dispatch stays in Rust for standard decoder registries; this
  cache is invalidated on public registry changes. Common JSON ID prefixes are
  accelerated while preserving Python's unusual integer/Unicode cases.
- Reduced temporary allocations and repeated index/metadata work in Python parsers.
- Deprecated parse APIs also use native acceleration; patchers and handlers use
  the registry bridge. Non-native-compatible readers retain Python in auto mode.
- Missing or incompatible native extensions automatically fall back to Python.

## [1.0.0] - 2026-08-10

### Added

- Binary catalog versions 1 through 3 are supported.
- Added `DecoderRegistry` and `BinaryDecodeContext` for per-parse custom binary
  decoders and serialized type aliases.
- Added checked provider-data helpers: `ResourceLocation.data_is()` and
  `ResourceLocation.data_as()`.
- Added catalog query helpers: `ContentCatalogData.locate()` and
  `ContentCatalogData.iter_locations()`.
- Added complete type information, a `py.typed` marker, strict Mypy checks, and
  modern setuptools package metadata.

### Changed

- Decoded provider data is exposed directly through `ResourceLocation.data`;
  its serialized Unity type is retained as private parser metadata.
- Replaced the new API's `patcher` and `handler` callbacks with explicit decoder
  registration. The deprecated `AddressablesTools` module continues to adapt the
  old callbacks and wrapped data model.
- Optimized JSON and binary catalog parsing with batched structure decoding and
  direct reads from immutable binary buffers.
- Improved parse failures so invalid indexes, negative lengths, malformed arrays,
  truncated data, and unsupported serialized objects use project exceptions.

### Fixed

- Dynamic string caches now account for the requested separator.
- Dynamic string reference cycles are detected instead of looping indefinitely.
- Internal ID prefix indexes and catalog key/location counts are validated.

### Deprecated

- The `AddressablesTools` import path remains available for legacy callers but
  emits `DeprecationWarning`; new code should import `addressablestools`.

## [0.2.0] - 2026-07-04

### Added

- Introduced the typed `addressablestools` package and safe JSON and binary readers.
- Added a compatibility layer for the original `AddressablesTools` package layout.
- Added automated tests, modern build configuration, and package documentation.

## [0.1.7] - 2025-05-12

### Added

- Initial JSON and binary Unity Addressables catalog reader.
- Added binary serialized-object patcher and handler callbacks.

[1.0.0]: https://github.com/anosu/AddressablesToolsPy/compare/3d0f3bb...v1.0.0
[1.1.0]: https://github.com/anosu/AddressablesToolsPy/compare/v1.0.0...v1.1.0
[0.2.0]: https://github.com/anosu/AddressablesToolsPy/compare/0dbf25e...3d0f3bb
[0.1.7]: https://github.com/anosu/AddressablesToolsPy/commits/0dbf25e
