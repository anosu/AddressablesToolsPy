# AddressablesToolsPy Rewrite Design

## Goal

Rewrite the project around a clean `addressablestools` package while preserving the existing `AddressablesTools` API through a removable compatibility layer.

The rewrite keeps the current supported behavior: reading Unity Addressables catalog files from JSON text and binary bytes, decoding built-in serialized objects, and supporting custom binary object patching and handling.

## Current Baseline

The existing code is concentrated under `src/AddressablesTools/` and exposes:

- `parse(data, patcher=None, handler=None)`
- `parse_json(data)`
- `parse_binary(data, patcher=None, handler=None)`
- `AddressablesTools.classes` exports for catalog models, binary reader, and decoders

Current tests pass only when `PYTHONPATH=src` is set. A plain `uv run pytest` cannot import `AddressablesTools` because the project does not configure pytest or editable installation behavior for the `src` layout.

The current implementation uses `orjson`, PascalCase module and attribute names, mutable classes with partially annotated fields, broad `Exception` errors, and parser/model classes that mix decoding, catalog assembly, and data storage responsibilities.

## Package Structure

The new implementation lives in `src/addressablestools/`:

```text
src/
  addressablestools/
    __init__.py
    parser.py
    models.py
    binary.py
    decoder.py
    catalog.py
    exceptions.py
    py.typed
  AddressablesTools/
    __init__.py
    classes.py
    _compat.py
```

The new package is the only implementation package. The old `AddressablesTools` package is a compatibility layer and must not be imported by `addressablestools`.

Future compatibility removal must require deleting `src/AddressablesTools/` and updating documentation only.

## Public API

New API:

```python
from addressablestools import parse, parse_json, parse_binary
from addressablestools.models import ContentCatalogData, ResourceLocation
```

Compatibility API:

```python
import AddressablesTools
from AddressablesTools.classes import ContentCatalogData, AssetBundleRequestOptions
```

The old API remains source-compatible for current documented usage, including PascalCase access such as:

```python
catalog.Resources
resource_location.Data.Object.Crc
resource_location.ProviderId
resource_location.InternalId
```

Compatibility code is centralized in `AddressablesTools/_compat.py` and re-exported from `AddressablesTools/__init__.py` and `AddressablesTools/classes.py`.

## Data Model

Core models use Python naming and complete type annotations. Value-like models must use dataclasses with slots, and immutable models must be frozen where practical.

Core model field names:

- `ContentCatalogData.version`
- `ContentCatalogData.locator_id`
- `ContentCatalogData.build_result_hash`
- `ContentCatalogData.instance_provider_data`
- `ContentCatalogData.scene_provider_data`
- `ContentCatalogData.resource_provider_data`
- `ContentCatalogData.provider_ids`
- `ContentCatalogData.internal_ids`
- `ContentCatalogData.keys`
- `ContentCatalogData.resource_types`
- `ContentCatalogData.internal_id_prefixes`
- `ContentCatalogData.resources`
- `ResourceLocation.internal_id`
- `ResourceLocation.provider_id`
- `ResourceLocation.dependency_key`
- `ResourceLocation.dependencies`
- `ResourceLocation.data`
- `ResourceLocation.hash_code`
- `ResourceLocation.dependency_hash_code`
- `ResourceLocation.primary_key`
- `ResourceLocation.type`
- `WrappedSerializedObject.type`
- `WrappedSerializedObject.object`
- `AssetBundleRequestOptions.hash`
- `AssetBundleRequestOptions.crc`
- `AssetBundleRequestOptions.common_info`
- `AssetBundleRequestOptions.bundle_name`
- `AssetBundleRequestOptions.bundle_size`

Compatibility PascalCase attributes are not added to the core implementation. They are exposed by the old package through adapters or compatibility subclasses.

## Parser And Catalog Assembly

Responsibilities are split as follows:

- `parser.py`: public entry points and input type dispatch
- `catalog.py`: JSON dictionary to model conversion and binary catalog assembly
- `binary.py`: binary readers, catalog header reading, encoded strings, offsets, cache behavior
- `decoder.py`: serialized object decoding and `AssetBundleRequestOptions` decoding
- `models.py`: data-only public model types
- `exceptions.py`: project exception hierarchy

`parse(data, patcher=None, handler=None)` dispatches `str` to `parse_json` and `bytes` to `parse_binary`. Other types raise a project exception with a clear message.

JSON parsing uses Python's standard library `json` module. `orjson` is removed from source code, dependencies, and lockfile resolution.

## Binary Object Customization

The existing binary customization behavior is preserved:

```python
type Patcher = Callable[[str], str | None]
type Handler = Callable[[CatalogBinaryReader, int, bool], object]
```

The default patcher returns the original match name. The default handler returns `None`.

If the patcher returns `None`, the handler is called with the reader, object offset, and default-object flag.

## Error Handling

The rewrite replaces broad `Exception` usage with a project exception hierarchy:

```python
AddressablesToolsError
CatalogParseError
UnsupportedCatalogVersionError
UnsupportedSerializedObjectError
BinaryReadError
```

Binary reads check for short reads and invalid offset arrays. User-facing failures must not leak `IndexError`, `struct.error`, or generic `Exception` for known invalid catalog conditions.

Unsupported binary catalog versions raise `UnsupportedCatalogVersionError`.

Unsupported serialized object match names raise `UnsupportedSerializedObjectError`.

## Tests

Tests are reorganized by behavior:

```text
tests/
  test_public_api.py
  test_json_parser.py
  test_binary_parser.py
  test_decoder.py
  test_binary_reader.py
  test_compat_api.py
  samples/
```

Required coverage:

- `addressablestools.parse_json` parses `tests/samples/catalog.json`.
- `addressablestools.parse_binary` parses `tests/samples/catalog.bin`.
- JSON and binary parsing agree on key bundle fields such as `crc`, `hash`, `bundle_name`, `internal_id`, and `provider_id`.
- `parse(str)` dispatches to JSON parsing.
- `parse(bytes)` dispatches to binary parsing.
- Unsupported `parse` input types raise a clear project exception.
- `orjson` is absent from source code and project dependencies.
- `AddressablesTools.parse`, `AddressablesTools.parse_json`, and `AddressablesTools.parse_binary` remain usable.
- `AddressablesTools.classes` still exports documented model and reader names.
- Compatibility PascalCase access works for documented examples, including `Resources`, `Data`, `Object`, `Crc`, `ProviderId`, and `InternalId`.
- Custom `patcher` and `handler` behavior is tested.
- Binary reader short reads, invalid offset array byte sizes, unsupported versions, and unsupported serialized object types are tested.

The old wall-clock performance assertions are removed. They are machine-dependent and conflict with replacing `orjson` with the standard library. Any future benchmark must be optional and not part of default correctness tests.

## Packaging And Tooling

`pyproject.toml` must be updated so a plain `uv run pytest` can discover the package from the `src` layout. The dependency list must not include `orjson`.

The package must include `py.typed` so downstream type checkers can consume annotations.

Ruff configuration may be added or updated where needed to support the rewritten package consistently.

## Migration Plan

Implementation must proceed in this order:

1. Add behavior tests for the new API and compatibility API.
2. Create the new `addressablestools` implementation package.
3. Port JSON parsing to standard-library `json`.
4. Port binary reader and decoder logic with explicit errors and complete annotations.
5. Port catalog assembly and models to Python-style names.
6. Replace old `AddressablesTools` implementation files with compatibility shims.
7. Update README examples to use `addressablestools` first and document legacy compatibility separately.
8. Update packaging configuration and remove `orjson`.
9. Run the full test suite with `uv run pytest`.

## Non-Goals

- Writing catalog files is not added.
- Support for new Unity Addressables binary catalog versions beyond the current version 1 and 2 behavior is not added.
- Benchmarking is not part of default tests.
- The compatibility layer does not need to preserve undocumented internals beyond the current public imports and README examples.
