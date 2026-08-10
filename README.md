# AddressablesToolsPy

Python library for reading Unity Addressables catalog files from JSON or binary catalog data.

Only reading is implemented.

Binary catalog versions 1 through 3 are supported. Version 3 support has not yet been
tested against a broad catalog corpus.

## Installation

```shell
pip install addressablestools
```

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

The legacy `AddressablesTools.classes` module is also provided for existing imports while migration is in progress.
