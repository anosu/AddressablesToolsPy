# AddressablesToolsPy Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the library into a typed, Pythonic `addressablestools` package while preserving the old `AddressablesTools` API through a removable compatibility layer.

**Architecture:** The new package owns all behavior and uses snake_case models, explicit parser modules, standard-library `json`, and project-specific exceptions. The old package becomes a thin adapter surface that maps documented PascalCase names to new models without being imported by the new package.

**Tech Stack:** Python 3.12, standard-library `json`, dataclasses with slots, pytest, ruff, uv, src-layout packaging.

---

## File Map

- Create: `src/addressablestools/__init__.py` public API exports.
- Create: `src/addressablestools/models.py` typed dataclass models and value objects.
- Create: `src/addressablestools/exceptions.py` project exception hierarchy.
- Create: `src/addressablestools/binary.py` `BinaryReader`, `CatalogBinaryReader`, header parsing, encoded strings, offset arrays.
- Create: `src/addressablestools/decoder.py` serialized object and built-in object decoders.
- Create: `src/addressablestools/catalog.py` JSON and binary catalog assembly.
- Create: `src/addressablestools/parser.py` parse entry points and input dispatch.
- Create: `src/addressablestools/py.typed` PEP 561 marker.
- Replace: `src/AddressablesTools/__init__.py` compatibility public API.
- Replace: `src/AddressablesTools/classes.py` compatibility class exports.
- Create: `src/AddressablesTools/_compat.py` PascalCase compatibility adapters.
- Delete after replacement: `src/AddressablesTools/Binary/`, `src/AddressablesTools/Catalog/`, `src/AddressablesTools/Classes/`, `src/AddressablesTools/JSON/`, `src/AddressablesTools/Reader/`, `src/AddressablesTools/constants.py`, `src/AddressablesTools/parser.py`.
- Replace: `tests/test_parse.py` with focused behavior tests.
- Create: `tests/conftest.py` shared fixtures and sample helpers.
- Create: `tests/test_public_api.py` public dispatch and package import tests.
- Create: `tests/test_models.py` model value behavior tests.
- Create: `tests/test_json_parser.py` JSON catalog behavior tests.
- Create: `tests/test_binary_parser.py` binary catalog behavior tests.
- Create: `tests/test_decoder.py` serialized object decoder tests.
- Create: `tests/test_binary_reader.py` binary reader error tests.
- Create: `tests/test_compat_api.py` old API compatibility tests.
- Modify: `pyproject.toml` remove `orjson`, configure src-layout pytest, optionally configure ruff.
- Modify: `uv.lock` refresh after dependency removal.
- Modify: `README.md` document new API first and legacy compatibility separately.

## Task 1: Package Import And Public API Tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_public_api.py`
- Modify: `pyproject.toml`
- Create: `src/addressablestools/__init__.py`
- Create: `src/addressablestools/parser.py`
- Create: `src/addressablestools/exceptions.py`
- Create: `src/addressablestools/py.typed`

- [ ] **Step 1: Write failing public API tests**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return Path(__file__).parent / "samples"


@pytest.fixture(scope="session")
def catalog_json_text(samples_dir: Path) -> str:
    return (samples_dir / "catalog.json").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def catalog_binary_bytes(samples_dir: Path) -> bytes:
    return (samples_dir / "catalog.bin").read_bytes()
```

Create `tests/test_public_api.py`:

```python
import pytest

import addressablestools
from addressablestools import parse, parse_binary, parse_json
from addressablestools.exceptions import CatalogParseError
from addressablestools.models import ContentCatalogData


def test_new_package_exports_parse_functions() -> None:
    assert addressablestools.parse is parse
    assert addressablestools.parse_json is parse_json
    assert addressablestools.parse_binary is parse_binary


def test_parse_dispatches_json_text(catalog_json_text: str) -> None:
    catalog = parse(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.resources


def test_parse_dispatches_binary_bytes(catalog_binary_bytes: bytes) -> None:
    catalog = parse(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.resources


def test_parse_rejects_unsupported_input_type() -> None:
    with pytest.raises(CatalogParseError, match="str or bytes"):
        parse({"not": "supported"})  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_public_api.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'addressablestools'`.

- [ ] **Step 3: Add src-layout pytest config and public API stubs**

In `pyproject.toml`, add:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `src/addressablestools/exceptions.py`:

```python
class AddressablesToolsError(Exception):
    """Base exception for addressablestools failures."""


class CatalogParseError(AddressablesToolsError):
    """Raised when catalog input cannot be parsed."""


class UnsupportedCatalogVersionError(CatalogParseError):
    """Raised when a binary catalog version is not supported."""


class UnsupportedSerializedObjectError(CatalogParseError):
    """Raised when a serialized object type is not supported."""


class BinaryReadError(CatalogParseError):
    """Raised when binary catalog data cannot be read safely."""
```

Create `src/addressablestools/parser.py` with temporary parsing stubs:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from addressablestools.exceptions import CatalogParseError

if TYPE_CHECKING:
    from addressablestools.binary import CatalogBinaryReader
    from addressablestools.models import ContentCatalogData

type Patcher = Callable[[str], str | None]
type Handler = Callable[["CatalogBinaryReader", int, bool], object]


def parse(data: str | bytes, patcher: Patcher | None = None, handler: Handler | None = None) -> "ContentCatalogData":
    if isinstance(data, str):
        return parse_json(data)
    if isinstance(data, bytes):
        return parse_binary(data, patcher=patcher, handler=handler)
    raise CatalogParseError(f"catalog input must be str or bytes, got {type(data).__name__}")


def parse_json(data: str) -> "ContentCatalogData":
    from addressablestools.catalog import parse_json_catalog

    return parse_json_catalog(data)


def parse_binary(data: bytes, patcher: Patcher | None = None, handler: Handler | None = None) -> "ContentCatalogData":
    from addressablestools.catalog import parse_binary_catalog

    return parse_binary_catalog(data, patcher=patcher, handler=handler)
```

Create `src/addressablestools/__init__.py`:

```python
from addressablestools.parser import Handler, Patcher, parse, parse_binary, parse_json

__version__ = "0.1.7"

__all__ = [
    "Handler",
    "Patcher",
    "parse",
    "parse_binary",
    "parse_json",
]
```

Create empty marker file `src/addressablestools/py.typed`.

- [ ] **Step 4: Run tests to verify expected remaining failure**

Run: `uv run pytest tests/test_public_api.py -q`

Expected: FAIL with `ModuleNotFoundError` for `addressablestools.models` or `addressablestools.catalog`, proving the tests now reach the new package.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml src/addressablestools tests/conftest.py tests/test_public_api.py
git commit -m "test: add new public api contract"
```

## Task 2: Typed Models

**Files:**
- Create: `tests/test_models.py`
- Create: `src/addressablestools/models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from addressablestools.models import (
    AssetBundleRequestOptions,
    AssetLoadMode,
    ClassJsonObject,
    Hash128,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
    TypeReference,
    WrappedSerializedObject,
)


def test_serialized_type_match_name_uses_short_assembly_name() -> None:
    serialized_type = SerializedType(
        assembly_name="Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
        class_name="UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions",
    )

    assert serialized_type.assembly_short_name == "Unity.ResourceManager"
    assert serialized_type.match_name == (
        "Unity.ResourceManager; "
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
    )


def test_hash128_from_four_uint32_values_matches_existing_byte_order() -> None:
    value = Hash128.from_uint32s(0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00)

    assert value.value == "4433221188776655ccbbaa9900ffeedd"


def test_resource_location_uses_pythonic_fields() -> None:
    resource_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    location = ResourceLocation(
        internal_id="bundle/path",
        provider_id="provider",
        dependency_key="dependency",
        dependencies=None,
        data=None,
        hash_code=123,
        dependency_hash_code=456,
        primary_key="primary",
        type=resource_type,
    )

    assert location.internal_id == "bundle/path"
    assert location.provider_id == "provider"
    assert location.primary_key == "primary"
    assert location.type == resource_type


def test_asset_bundle_request_options_defaults_are_typed() -> None:
    options = AssetBundleRequestOptions()

    assert options.hash == ""
    assert options.crc == 0
    assert options.bundle_name is None
    assert options.bundle_size == 0
    assert options.common_info is None


def test_wrapped_serialized_object_keeps_type_and_object() -> None:
    serialized_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    wrapped = WrappedSerializedObject(type=serialized_type, object=TypeReference("clsid"))

    assert wrapped.type is serialized_type
    assert wrapped.object == TypeReference("clsid")


def test_catalog_related_models_are_importable() -> None:
    serialized_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    obj = ObjectInitializationData(id="id", object_type=serialized_type, data=None)
    json_obj = ClassJsonObject(type=serialized_type, json_text="{}")

    assert obj.id == "id"
    assert json_obj.type == serialized_type
    assert AssetLoadMode.ALL_PACKED_ASSETS_AND_DEPENDENCIES.value == 1
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_models.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'addressablestools.models'`.

- [ ] **Step 3: Implement typed models**

Create `src/addressablestools/models.py` with dataclasses for:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import struct
from typing import Generic, TypeVar


@dataclass(frozen=True, slots=True)
class SerializedType:
    assembly_name: str | None
    class_name: str | None

    @property
    def assembly_short_name(self) -> str:
        if self.assembly_name is None:
            raise ValueError("assembly_name is required")
        return self.assembly_name.split(",", 1)[0]

    @property
    def match_name(self) -> str:
        if self.class_name is None:
            raise ValueError("class_name is required")
        return f"{self.assembly_short_name}; {self.class_name}"


@dataclass(frozen=True, slots=True)
class TypeReference:
    clsid: str


@dataclass(frozen=True, slots=True)
class Hash128:
    value: str

    @classmethod
    def from_uint32s(cls, first: int, second: int, third: int, fourth: int) -> "Hash128":
        return cls(struct.pack("<IIII", first, second, third, fourth).hex())


@dataclass(frozen=True, slots=True)
class ClassJsonObject:
    type: SerializedType
    json_text: str


@dataclass(frozen=True, slots=True)
class ObjectInitializationData:
    id: str | None
    object_type: SerializedType
    data: str | None


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class WrappedSerializedObject(Generic[T]):
    type: SerializedType
    object: T


class AssetLoadMode(Enum):
    REQUESTED_ASSET_AND_DEPENDENCIES = 0
    ALL_PACKED_ASSETS_AND_DEPENDENCIES = 1


@dataclass(slots=True)
class CommonInfo:
    timeout: int = 0
    redirect_limit: int = 0
    retry_count: int = 0
    asset_load_mode: AssetLoadMode = AssetLoadMode.ALL_PACKED_ASSETS_AND_DEPENDENCIES
    chunked_transfer: bool = False
    use_crc_for_cached_bundle: bool = False
    use_unity_web_request_for_local_bundles: bool = False
    clear_other_cached_versions_when_loaded: bool = False
    version: int = 0


@dataclass(slots=True)
class AssetBundleRequestOptions:
    hash: str = ""
    crc: int = 0
    common_info: CommonInfo | None = None
    bundle_name: str | None = None
    bundle_size: int = 0


SerializedObject = (
    ClassJsonObject
    | TypeReference
    | Hash128
    | int
    | str
    | bool
    | WrappedSerializedObject[AssetBundleRequestOptions]
    | None
)


@dataclass(slots=True)
class ResourceLocation:
    internal_id: str | None = None
    provider_id: str | None = None
    dependency_key: object = None
    dependencies: list["ResourceLocation"] | None = None
    data: SerializedObject = None
    hash_code: int = 0
    dependency_hash_code: int = 0
    primary_key: str | None = None
    type: SerializedType | None = None


@dataclass(slots=True)
class ContentCatalogData:
    version: int = 0
    locator_id: str | None = None
    build_result_hash: str | None = None
    instance_provider_data: ObjectInitializationData | None = None
    scene_provider_data: ObjectInitializationData | None = None
    resource_provider_data: list[ObjectInitializationData] = field(default_factory=list)
    provider_ids: list[str] = field(default_factory=list)
    internal_ids: list[str] = field(default_factory=list)
    keys: list[str] | None = None
    resource_types: list[SerializedType] = field(default_factory=list)
    internal_id_prefixes: list[str] = field(default_factory=list)
    resources: dict[object, list[ResourceLocation]] = field(default_factory=dict)


__all__ = [
    "AssetBundleRequestOptions",
    "AssetLoadMode",
    "ClassJsonObject",
    "CommonInfo",
    "ContentCatalogData",
    "Hash128",
    "ObjectInitializationData",
    "ResourceLocation",
    "SerializedObject",
    "SerializedType",
    "TypeReference",
    "WrappedSerializedObject",
]
```

- [ ] **Step 4: Run tests to verify green for models**

Run: `uv run pytest tests/test_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/addressablestools/models.py tests/test_models.py
git commit -m "feat: add typed catalog models"
```

## Task 3: Binary Reader And Header

**Files:**
- Create: `tests/test_binary_reader.py`
- Create: `src/addressablestools/binary.py`

- [ ] **Step 1: Write failing binary reader tests**

Create `tests/test_binary_reader.py`:

```python
from io import BytesIO
import struct

import pytest

from addressablestools.binary import BinaryReader, CatalogBinaryHeader, CatalogBinaryReader, UINT32_MAX
from addressablestools.exceptions import BinaryReadError, UnsupportedCatalogVersionError


def test_binary_reader_raises_binary_read_error_on_short_read() -> None:
    reader = BinaryReader(BytesIO(b"\x01\x02"))

    with pytest.raises(BinaryReadError, match="expected 4 bytes"):
        reader.read_int32()


def test_catalog_reader_rejects_invalid_offset_array_byte_size() -> None:
    data = struct.pack("<i", 3) + b"abc"
    reader = CatalogBinaryReader(BytesIO(data))

    with pytest.raises(BinaryReadError, match="multiple of 4"):
        reader.read_offset_array(4)


def test_catalog_reader_returns_empty_offset_array_for_uint32_max() -> None:
    reader = CatalogBinaryReader(BytesIO(b""))

    assert reader.read_offset_array(UINT32_MAX) == []


def test_binary_header_rejects_unsupported_version() -> None:
    header_bytes = struct.pack("<ii", 0, 99) + b"\x00" * 20
    reader = CatalogBinaryReader(BytesIO(header_bytes))

    with pytest.raises(UnsupportedCatalogVersionError, match="Only versions 1 and 2"):
        CatalogBinaryHeader.read(reader)
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_binary_reader.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'addressablestools.binary'`.

- [ ] **Step 3: Implement binary reader**

Create `src/addressablestools/binary.py` with:

- `UINT32_MAX = 4294967295`
- `UINT32_MAX_MINUS_ONE = 4294967294`
- `BinaryReader` using `read_exact(count)` before all struct unpacking.
- `CatalogBinaryReader` with typed `patcher`, `handler`, object cache, `read_encoded_string`, `read_offset_array`, and `read_custom`.
- `CatalogBinaryHeader.read(reader)` that supports versions 1 and 2 and raises `UnsupportedCatalogVersionError`.

Preserve the existing encoded string rules:

```python
unicode = (encoded_offset & 0x80000000) != 0
dynamic = (encoded_offset & 0x40000000) != 0 and dynamic_separator != "\0"
offset = encoded_offset & 0x3FFFFFFF
```

Preserve version 2 dynamic-string reversal:

```python
if len(parts) > 1 and self.version > 1:
    parts.reverse()
```

- [ ] **Step 4: Run tests to verify green for reader**

Run: `uv run pytest tests/test_binary_reader.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/addressablestools/binary.py tests/test_binary_reader.py
git commit -m "feat: add safe binary catalog reader"
```

## Task 4: Serialized Object Decoder

**Files:**
- Create: `tests/test_decoder.py`
- Create: `src/addressablestools/decoder.py`

- [ ] **Step 1: Write failing decoder tests**

Create `tests/test_decoder.py`:

```python
from io import BytesIO
import json
import struct

import pytest

from addressablestools.binary import BinaryReader, CatalogBinaryReader, UINT32_MAX
from addressablestools.decoder import SerializedObjectDecoder
from addressablestools.exceptions import UnsupportedSerializedObjectError
from addressablestools.models import AssetBundleRequestOptions, Hash128, TypeReference, WrappedSerializedObject


def test_decode_v1_ascii_string() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.ASCII_STRING.value])
    payload += struct.pack("<i", 5) + b"hello"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == "hello"


def test_decode_v1_hash128() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.HASH128.value])
    payload += bytes([4]) + b"abcd"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == Hash128("abcd")


def test_decode_v1_type_reference() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.TYPE.value])
    payload += bytes([5]) + b"clsid"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == TypeReference("clsid")


def test_asset_bundle_request_options_json_decodes_standard_library_json() -> None:
    options_json = json.dumps(
        {
            "m_Hash": "hash",
            "m_Crc": 123,
            "m_BundleName": "bundle",
            "m_BundleSize": 456,
            "m_Timeout": 1,
            "m_RedirectLimit": 2,
            "m_RetryCount": 3,
            "m_ChunkedTransfer": False,
            "m_AssetLoadMode": 1,
            "m_UseCrcForCachedBundle": True,
            "m_UseUWRForLocalBundles": False,
            "m_ClearOtherCachedVersionsWhenLoaded": True,
        }
    )

    options = SerializedObjectDecoder.decode_asset_bundle_request_options_json(options_json)

    assert isinstance(options, AssetBundleRequestOptions)
    assert options.hash == "hash"
    assert options.crc == 123
    assert options.bundle_name == "bundle"
    assert options.bundle_size == 456
    assert options.common_info is not None
    assert options.common_info.version == 3


def test_decode_v2_calls_handler_when_patcher_returns_none() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32), patcher=lambda _: None, handler=lambda _reader, offset, is_default: (offset, is_default))
    reader.read_custom = lambda _offset, fetch: fetch()  # type: ignore[method-assign]
    reader.seek = lambda _offset, _whence=0: None  # type: ignore[method-assign]
    reader.read_uint32 = iter([8, UINT32_MAX]).__next__  # type: ignore[method-assign]
    reader.read_serialized_type = lambda _offset: type("FakeType", (), {"match_name": "Custom; System.Int32"})()  # type: ignore[attr-defined, method-assign]

    assert SerializedObjectDecoder.decode_v2(reader, 0) == (UINT32_MAX, True)


def test_decode_v2_raises_for_unsupported_type() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    reader.read_custom = lambda _offset, fetch: fetch()  # type: ignore[method-assign]
    reader.seek = lambda _offset, _whence=0: None  # type: ignore[method-assign]
    reader.read_uint32 = iter([8, UINT32_MAX]).__next__  # type: ignore[method-assign]
    reader.read_serialized_type = lambda _offset: type("FakeType", (), {"match_name": "Custom; Unsupported"})()  # type: ignore[attr-defined, method-assign]

    with pytest.raises(UnsupportedSerializedObjectError, match="Custom; Unsupported"):
        SerializedObjectDecoder.decode_v2(reader, 0)
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_decoder.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'addressablestools.decoder'`.

- [ ] **Step 3: Implement decoder**

Create `src/addressablestools/decoder.py` with:

- `SerializedObjectDecoder.ObjectType` enum matching the old numeric values.
- Constants for built-in match names:
  - `mscorlib; System.Int32`
  - `mscorlib; System.Int64`
  - `mscorlib; System.Boolean`
  - `mscorlib; System.String`
  - `UnityEngine.CoreModule; UnityEngine.Hash128`
  - `Unity.ResourceManager; UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions`
- `decode_v1(reader: BinaryReader) -> object`
- `decode_v2(reader: CatalogBinaryReader, offset: int) -> object`
- `decode_asset_bundle_request_options_json(json_text: str) -> AssetBundleRequestOptions`
- `read_string1`, `read_string4`, `read_string4_unicode`

Use `json.loads` from the standard library. If an AssetBundleRequestOptions JSON string is invalid or empty, return default `AssetBundleRequestOptions()`.

- [ ] **Step 4: Run tests to verify green for decoder**

Run: `uv run pytest tests/test_decoder.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/addressablestools/decoder.py tests/test_decoder.py
git commit -m "feat: add serialized object decoder"
```

## Task 5: JSON Catalog Parser

**Files:**
- Create: `tests/test_json_parser.py`
- Create: `src/addressablestools/catalog.py`

- [ ] **Step 1: Write failing JSON parser tests**

Create `tests/test_json_parser.py`:

```python
from addressablestools import parse_json
from addressablestools.models import AssetBundleRequestOptions, ContentCatalogData, WrappedSerializedObject


def first_bundle(catalog: ContentCatalogData) -> tuple[str, WrappedSerializedObject[AssetBundleRequestOptions]]:
    for key, locations in catalog.resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            data = locations[0].data
            assert isinstance(data, WrappedSerializedObject)
            assert isinstance(data.object, AssetBundleRequestOptions)
            return key, data
    raise AssertionError("sample catalog must contain at least one bundle")


def test_parse_json_returns_pythonic_catalog(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.locator_id
    assert catalog.provider_ids
    assert catalog.internal_ids
    assert catalog.resource_types
    assert catalog.resources


def test_parse_json_decodes_bundle_request_options(catalog_json_text: str) -> None:
    key, wrapped = first_bundle(parse_json(catalog_json_text))

    assert key.endswith(".bundle")
    assert wrapped.object.crc > 0
    assert wrapped.object.hash
    assert wrapped.object.bundle_name
    assert wrapped.object.bundle_size > 0


def test_parse_json_expands_internal_id_prefixes(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)
    key, _wrapped = first_bundle(catalog)
    location = catalog.resources[key][0]

    assert location.internal_id is not None
    assert "#" not in location.internal_id[:3]
    assert location.provider_id is not None
    assert location.primary_key is not None
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_json_parser.py -q`

Expected: FAIL because `addressablestools.catalog` or `parse_json_catalog` does not exist.

- [ ] **Step 3: Implement JSON catalog parsing**

Create `src/addressablestools/catalog.py` with:

- `parse_json_catalog(data: str) -> ContentCatalogData`
- `parse_binary_catalog(data: bytes, patcher: Patcher | None = None, handler: Handler | None = None) -> ContentCatalogData` temporary `raise NotImplementedError("binary parsing is implemented in Task 6")`
- helper functions:
  - `_serialized_type_from_json(obj: Mapping[str, object]) -> SerializedType`
  - `_object_initialization_data_from_json(obj: Mapping[str, object]) -> ObjectInitializationData`
  - `_decode_json_resources(catalog: ContentCatalogData, raw: Mapping[str, object]) -> dict[object, list[ResourceLocation]]`
  - `_apply_internal_id_prefix(internal_id: str, prefixes: list[str]) -> str`

Port the old JSON resource algorithm exactly:

- Base64 decode `m_BucketDataString`, `m_KeyDataString`, `m_EntryDataString`, and `m_ExtraDataString`.
- Read bucket count, bucket offsets, and entry indexes.
- Decode keys with `SerializedObjectDecoder.decode_v1`.
- Decode entry records as seven int32 values.
- Use `m_Keys[primary_key_index]` when `m_Keys` exists; otherwise use the decoded key.
- Decode extra object data when `data_index >= 0`.
- Build `catalog.resources` from each bucket's entry list.

- [ ] **Step 4: Run tests to verify green for JSON parser**

Run: `uv run pytest tests/test_json_parser.py tests/test_public_api.py::test_parse_dispatches_json_text -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/addressablestools/catalog.py tests/test_json_parser.py
git commit -m "feat: parse json addressables catalogs"
```

## Task 6: Binary Catalog Parser

**Files:**
- Create: `tests/test_binary_parser.py`
- Modify: `src/addressablestools/binary.py`
- Modify: `src/addressablestools/catalog.py`
- Modify: `src/addressablestools/decoder.py`

- [ ] **Step 1: Write failing binary parser tests**

Create `tests/test_binary_parser.py`:

```python
from addressablestools import parse_binary, parse_json
from addressablestools.models import AssetBundleRequestOptions, ContentCatalogData, WrappedSerializedObject


def first_bundle(catalog: ContentCatalogData) -> tuple[str, WrappedSerializedObject[AssetBundleRequestOptions]]:
    for key, locations in catalog.resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            data = locations[0].data
            assert isinstance(data, WrappedSerializedObject)
            assert isinstance(data.object, AssetBundleRequestOptions)
            return key, data
    raise AssertionError("sample catalog must contain at least one bundle")


def test_parse_binary_returns_pythonic_catalog(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.version in {1, 2}
    assert catalog.resources


def test_parse_binary_decodes_bundle_request_options(catalog_binary_bytes: bytes) -> None:
    key, wrapped = first_bundle(parse_binary(catalog_binary_bytes))

    assert key.endswith(".bundle")
    assert wrapped.object.crc > 0
    assert wrapped.object.hash
    assert wrapped.object.bundle_name
    assert wrapped.object.bundle_size > 0


def test_json_and_binary_catalogs_agree_on_first_bundle(catalog_json_text: str, catalog_binary_bytes: bytes) -> None:
    json_key, json_wrapped = first_bundle(parse_json(catalog_json_text))
    binary_key, binary_wrapped = first_bundle(parse_binary(catalog_binary_bytes))

    assert binary_key == json_key
    assert binary_wrapped.object.crc == json_wrapped.object.crc
    assert binary_wrapped.object.hash == json_wrapped.object.hash
    assert binary_wrapped.object.bundle_name == json_wrapped.object.bundle_name
    assert binary_wrapped.object.bundle_size == json_wrapped.object.bundle_size


def test_parse_binary_accepts_custom_patcher_and_handler(catalog_binary_bytes: bytes) -> None:
    calls: list[str] = []

    def patcher(match_name: str) -> str | None:
        calls.append(match_name)
        return match_name

    catalog = parse_binary(catalog_binary_bytes, patcher=patcher)

    assert catalog.resources
    assert calls
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_binary_parser.py -q`

Expected: FAIL because `parse_binary_catalog` is not implemented.

- [ ] **Step 3: Implement binary catalog parsing**

Update `src/addressablestools/binary.py`:

- Add `read_serialized_type(offset: int) -> SerializedType`.
- Ensure `read_custom` caches by offset and returns the cached object.

Update `src/addressablestools/catalog.py`:

- Implement `parse_binary_catalog`.
- Read `CatalogBinaryHeader`.
- Populate catalog metadata from header offsets.
- Read initialization object offsets with `read_offset_array`.
- Read key/location pairs from `header.keys_offset`.
- Decode keys with `SerializedObjectDecoder.decode_v2`.
- Read location lists with `read_offset_array`.
- Decode `ResourceLocation` objects with a helper `_resource_location_from_binary(reader, offset)`.

Update `src/addressablestools/decoder.py`:

- Implement binary `AssetBundleRequestOptions` decoding.
- Implement binary `CommonInfo` decoding.
- Preserve defaults for default objects.

- [ ] **Step 4: Run tests to verify green for binary parser**

Run: `uv run pytest tests/test_binary_parser.py tests/test_public_api.py::test_parse_dispatches_binary_bytes -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/addressablestools/binary.py src/addressablestools/catalog.py src/addressablestools/decoder.py tests/test_binary_parser.py
git commit -m "feat: parse binary addressables catalogs"
```

## Task 7: Legacy Compatibility Layer

**Files:**
- Create: `tests/test_compat_api.py`
- Create: `src/AddressablesTools/_compat.py`
- Replace: `src/AddressablesTools/__init__.py`
- Replace: `src/AddressablesTools/classes.py`
- Delete: old implementation subdirectories after tests pass

- [ ] **Step 1: Write failing compatibility tests**

Create `tests/test_compat_api.py`:

```python
import AddressablesTools
from AddressablesTools.classes import AssetBundleRequestOptions, ContentCatalogData, CatalogBinaryReader


def test_legacy_parse_json_returns_pascal_case_catalog(catalog_json_text: str) -> None:
    catalog = AddressablesTools.parse_json(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.Resources
    assert catalog.ProviderIds
    assert catalog.InternalIds


def test_legacy_parse_binary_returns_pascal_case_bundle_data(catalog_binary_bytes: bytes) -> None:
    catalog = AddressablesTools.parse_binary(catalog_binary_bytes)

    for key, locations in catalog.Resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            location = locations[0]
            assert location.InternalId
            assert location.ProviderId
            assert isinstance(location.Data.Object, AssetBundleRequestOptions)
            assert location.Data.Object.Crc > 0
            assert location.Data.Object.Hash
            return
    raise AssertionError("sample catalog must contain at least one bundle")


def test_legacy_parse_dispatches_to_new_parser(catalog_json_text: str, catalog_binary_bytes: bytes) -> None:
    assert AddressablesTools.parse(catalog_json_text).Resources
    assert AddressablesTools.parse(catalog_binary_bytes).Resources


def test_legacy_classes_exports_catalog_binary_reader() -> None:
    assert CatalogBinaryReader.__name__ == "CatalogBinaryReader"
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_compat_api.py -q`

Expected: FAIL because the old package still returns old implementation objects or lacks new compatibility wrappers.

- [ ] **Step 3: Implement compatibility wrappers**

Create `src/AddressablesTools/_compat.py`:

- Adapter classes:
  - `CompatCatalog`
  - `CompatResourceLocation`
  - `CompatWrappedSerializedObject`
  - `CompatAssetBundleRequestOptions`
  - `CompatCommonInfo`
  - `CompatSerializedType`
  - `CompatObjectInitializationData`
  - `CompatClassJsonObject`
  - `CompatHash128`
  - `CompatTypeReference`
- Functions:
  - `wrap_legacy(value: object) -> object`
  - `parse(data, patcher=None, handler=None)`
  - `parse_json(data)`
  - `parse_binary(data, patcher=None, handler=None)`

Each adapter owns a new-model object and exposes documented PascalCase properties only. Example property mapping:

```python
class CompatResourceLocation:
    def __init__(self, location: ResourceLocation) -> None:
        self._location = location

    @property
    def InternalId(self) -> str | None:
        return self._location.internal_id

    @property
    def ProviderId(self) -> str | None:
        return self._location.provider_id

    @property
    def Data(self) -> object:
        return wrap_legacy(self._location.data)
```

Replace `src/AddressablesTools/__init__.py`:

```python
from AddressablesTools._compat import parse, parse_binary, parse_json

Parser = None
__version__ = "0.1.7"

__all__ = ["classes", "parse", "parse_json", "parse_binary", "Parser"]
```

Replace `src/AddressablesTools/classes.py` with compatibility exports:

```python
from AddressablesTools._compat import (
    CompatAssetBundleRequestOptions as AssetBundleRequestOptions,
    CompatCatalog as ContentCatalogData,
    CompatClassJsonObject as ClassJsonObject,
    CompatHash128 as Hash128,
    CompatObjectInitializationData as ObjectInitializationData,
    CompatResourceLocation as ResourceLocation,
    CompatSerializedType as SerializedType,
    CompatTypeReference as TypeReference,
    CompatWrappedSerializedObject as WrappedSerializedObject,
)
from addressablestools.binary import CatalogBinaryReader
from addressablestools.decoder import SerializedObjectDecoder

__all__ = [
    "WrappedSerializedObject",
    "ContentCatalogData",
    "ClassJsonObject",
    "SerializedType",
    "ResourceLocation",
    "ObjectInitializationData",
    "TypeReference",
    "Hash128",
    "AssetBundleRequestOptions",
    "SerializedObjectDecoder",
    "CatalogBinaryReader",
]
```

- [ ] **Step 4: Run tests to verify green for compatibility**

Run: `uv run pytest tests/test_compat_api.py -q`

Expected: PASS.

- [ ] **Step 5: Delete obsolete old implementation files**

Delete these paths after compatibility tests pass:

```text
src/AddressablesTools/Binary/
src/AddressablesTools/Catalog/
src/AddressablesTools/Classes/
src/AddressablesTools/JSON/
src/AddressablesTools/Reader/
src/AddressablesTools/constants.py
src/AddressablesTools/parser.py
```

Run: `uv run pytest tests/test_compat_api.py tests/test_json_parser.py tests/test_binary_parser.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/AddressablesTools tests/test_compat_api.py
git add -u src/AddressablesTools
git commit -m "feat: replace legacy package with compatibility layer"
```

## Task 8: Packaging, Dependency Cleanup, README

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `README.md`
- Create or modify: `tests/test_packaging.py`
- Delete: `tests/test_parse.py`

- [ ] **Step 1: Write failing packaging tests**

Create `tests/test_packaging.py`:

```python
from pathlib import Path


def test_orjson_is_removed_from_project_files() -> None:
    root = Path(__file__).parents[1]
    searchable = [
        root / "pyproject.toml",
        root / "src" / "addressablestools",
        root / "src" / "AddressablesTools",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for item in searchable
        for path in ([item] if item.is_file() else item.rglob("*.py"))
    )

    assert "orjson" not in text


def test_readme_documents_new_package_first() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "from addressablestools import parse" in readme
    assert "Legacy compatibility" in readme
```

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_packaging.py -q`

Expected: FAIL because `pyproject.toml` and README still mention old dependency or old API first.

- [ ] **Step 3: Update project metadata and docs**

Update `pyproject.toml`:

```toml
[project]
name = "addressablestools"
version = "0.1.7"
authors = [{ name = "Jitsu", email = "jitsu233@gmail.com" }]
description = "Python library for reading Unity Addressables catalog files"
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8.3.5", "ruff>=0.11.7"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

Update README examples to import from `addressablestools` first and add a `Legacy compatibility` section showing `import AddressablesTools` for old callers.

Delete old `tests/test_parse.py` after equivalent behavior is covered by focused tests.

Run: `uv lock`

Expected: `uv.lock` no longer includes `orjson`.

- [ ] **Step 4: Run tests to verify green for packaging**

Run: `uv run pytest tests/test_packaging.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml uv.lock README.md tests/test_packaging.py tests/test_parse.py
git commit -m "chore: remove orjson and document new package"
```

## Task 9: Full Verification And Cleanup

**Files:**
- All touched project files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run ruff check**

Run: `uv run ruff check .`

Expected: no lint errors.

- [ ] **Step 3: Verify no old implementation imports remain**

Run: `rg "from \\.|AddressablesTools\\.(Binary|Catalog|Classes|JSON|Reader)|orjson|type: ignore" src tests pyproject.toml README.md`

Expected:

- No `orjson` matches.
- No imports from deleted old implementation packages.
- No new `type: ignore` unless narrowly justified in tests.

- [ ] **Step 4: Verify worktree state**

Run: `git status --short`

Expected: clean worktree after all task commits.

- [ ] **Step 5: Final commit if verification-only fixes were required**

If Step 1, Step 2, or Step 3 required cleanup changes, commit them:

```bash
git add .
git commit -m "chore: finalize addressablestools rewrite"
```

If no cleanup changes were required, do not create an empty commit.

## Self-Review

- Spec coverage: The plan covers the new package, old compatibility layer, standard-library `json`, type annotations, error hierarchy, packaging, README, and behavior tests.
- Unfinished-marker scan: No unfinished markers are present. Tasks name exact files, commands, and expected outcomes.
- Type consistency: Public names match the design: new fields use `snake_case`, compatibility fields use PascalCase, and parser customization keeps `Patcher` and `Handler`.
