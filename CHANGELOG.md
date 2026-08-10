# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
[0.2.0]: https://github.com/anosu/AddressablesToolsPy/compare/0dbf25e...3d0f3bb
[0.1.7]: https://github.com/anosu/AddressablesToolsPy/commits/0dbf25e
