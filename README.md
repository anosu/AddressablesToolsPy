# AddressablesToolsPy

Python library for reading Unity Addressables catalog files from JSON or binary catalog data.

Only reading is implemented.

Binary catalog versions 1 through 3 are supported. Version 3 support has not yet been
tested against a broad catalog corpus.

## Installation

```shell
pip install addressablestools
```

Version 1.1 includes the Python API and Rust accelerator in the same wheel, with
no separate runtime dependency. Standard CPython 3.12+ on the
[supported platforms](PUBLISHING.md#platforms) installs a prebuilt wheel without a
Rust toolchain. Building from source requires Rust 1.88+ and a platform linker.
`backend="python"` still selects the reference parser.

## Parse JSON catalogs

```python
from pathlib import Path

from addressablestools import AssetBundleRequestOptions, parse_json


data = Path("tests/samples/catalog.json").read_text(encoding="utf-8")
catalog = parse_json(data)

for key, locations in catalog.resources.items():
    if not isinstance(key, str) or not key.endswith(".bundle"):
        continue

    options = locations[0].data_as(AssetBundleRequestOptions)
    print(f"Bundle {key}, Crc: {options.crc}, Hash: {options.hash}")
```

## Parse binary catalogs

```python
from pathlib import Path

from addressablestools import parse_binary


catalog = parse_binary(Path("tests/samples/catalog.bin").read_bytes())
location = catalog.resources["Anim/Network"][0]

print(location.primary_key)
print(location.internal_id)
print(location.provider_id)
print(location.type.class_name if location.type else None)
```

For reproducible parsing measurements and optimization results, see
[the catalog benchmarks](benchmarks/README.md).

To build the package, including its [Rust module](native/README.md), from this checkout:

```shell
uv sync --locked
```

`parse()`, `parse_binary()`, and `parse_json()` use it automatically
for supported calls. Select the backend per call:

```python
from pathlib import Path
from addressablestools import available_backends, parse_json

data = Path("tests/samples/catalog.json").read_text(encoding="utf-8")
print(available_backends("json"))  # ("python", "rust") when the JSON accelerator is installed
catalog = parse_json(data, backend="auto")
reference = parse_json(data, backend="python")
```

`auto` uses Python when the bundled extension is missing or incompatible.
`DecoderRegistry` is supported: standard registries keep built-in dispatch in Rust
and call the Python object decoder only for custom
decoders. Calls to `register()` and `alias()` invalidate cached dispatch decisions.
`rust` requires native support and raises
`NativeBackendUnavailableError` instead of silently falling back. Backend selection
is local to each call. The deprecated API accepts the same keyword; patchers and
handlers use the same registry bridge.
The previous `native` extra remains accepted as a compatibility alias.

## Auto-detect catalog format

`parse()` dispatches `str` input to JSON parsing and `bytes` input to binary parsing.

```python
from pathlib import Path

from addressablestools import parse


json_catalog = parse(Path("tests/samples/catalog.json").read_text(encoding="utf-8"))
binary_catalog = parse(Path("tests/samples/catalog.bin").read_bytes())

print(len(json_catalog.resources))
print(len(binary_catalog.resources))
```

## Query resource locations

Catalog resources are exposed with Python-style names.

```python
from pathlib import Path

from addressablestools import parse_json


catalog = parse_json(Path("tests/samples/catalog.json").read_text(encoding="utf-8"))
asset_key = "Assets/Paripari/AddressableAssets/VFX Texture Assets/ParticleTextures/sparkle.png"
asset_location = catalog.locate(asset_key)[0]

print(asset_location.primary_key)
print(asset_location.internal_id)
print(asset_location.provider_id)

if asset_location.dependency_key is not None:
    dependency_location = catalog.locate(asset_location.dependency_key)[0]
    print(dependency_location.primary_key)
    print(dependency_location.internal_id)
```

## Custom binary object handling

Binary catalogs may contain custom serialized object types. A decoder registry can alias a
custom type to a supported built-in type or register a decoder function for that type.

```python
from pathlib import Path

from addressablestools import DecoderRegistry, parse_binary
from addressablestools.decoder import SerializedObjectDecoder


registry = DecoderRegistry()
registry.alias(
    "Custom.Assembly; Custom.AssetBundleRequestOptions",
    SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME,
)


catalog = parse_binary(Path("catalog.bin").read_bytes(), registry=registry)
```

Decoder functions receive the exact serialized type together with the object offset.
These calls use the bundled Rust resource traversal automatically. Add
`backend="rust"` to require it or
`backend="python"` to use the reference parser. Decoder functions keep running in
Python with the same reader and shared object cache. Registry subclasses and
instance overrides of resolution methods retain the per-object Python bridge.

```python
from dataclasses import dataclass
from pathlib import Path

from addressablestools import BinaryDecodeContext, DecoderRegistry, parse_binary


@dataclass(frozen=True)
class CustomInt32Value:
    value: int


registry = DecoderRegistry()


@registry.register("Custom.Assembly; Custom.Int32Value")
def decode_custom_int32(context: BinaryDecodeContext) -> CustomInt32Value:
    if context.is_default:
        return CustomInt32Value(0)
    context.reader.seek(context.offset)
    return CustomInt32Value(context.reader.read_int32())


catalog = parse_binary(Path("catalog.bin").read_bytes(), registry=registry)
```

## Changelog

See the [changelog](https://github.com/anosu/AddressablesToolsPy/blob/main/CHANGELOG.md)
for release history and upgrade notes.

## Deprecated API

The old `AddressablesTools` import path is deprecated as of `0.2.0`. It remains available as a thin compatibility layer, but new code should import `addressablestools` directly. Calling `AddressablesTools.parse()`, `AddressablesTools.parse_json()`, or `AddressablesTools.parse_binary()` emits a `DeprecationWarning`.

## Legacy compatibility

Existing callers can keep using the old import path while migrating:

```python
from pathlib import Path

import AddressablesTools
from AddressablesTools.classes import AssetBundleRequestOptions


catalog = AddressablesTools.parse_json(Path("tests/samples/catalog.json").read_text("utf-8"))
for key, locations in catalog.Resources.items():
    if isinstance(key, str) and key.endswith(".bundle"):
        assert isinstance(locations[0].Data.Object, AssetBundleRequestOptions)
        print(locations[0].Data.Object.Crc)
```

`catalog.Resources` lazily creates a normal dictionary of legacy location lists
on first access and reuses it afterward. Repeated lookups such as
`catalog.Resources[key][0].InternalId` no longer rebuild the entire catalog.

The dictionary and lists are a cached snapshot: edits to them persist across
accesses on that wrapper, without changing the underlying modern resource mapping.
Location properties still read the underlying objects' current fields. If you
change the modern resource mapping or want to discard snapshot edits, use
`del catalog.Resources`; the next access rebuilds it. Separate catalog wrappers
have separate snapshots. For new code, prefer `addressablestools` and its
`catalog.resources` mapping.

Within a resource snapshot, aliases for the same underlying location share one
legacy location wrapper; each key still has its own list. `location.Dependencies`
also caches a list snapshot and automatically rebuilds it if the underlying list
is replaced. After in-place edits to the underlying list, or to discard edits to
the snapshot, use `del location.Dependencies` to rebuild it on the next access.
When aliases share a location wrapper, they also share this dependency snapshot.

Repeated `location.Data.Object`, `location.Data.Type`, `location.Type`, and bundle
`ComInfo` reads reuse metadata wrappers. Replacing the underlying data, type, or
common-info object refreshes the relevant wrapper automatically; scalar field
changes remain visible. Lists and dictionaries returned by custom decoders keep
their existing behavior: each access wraps their current contents.

The legacy `AddressablesTools.classes` module is also provided for existing imports while migration is in progress.
