# AddressablesToolsPy

Python library for reading Unity Addressables catalog files from JSON or binary catalog data.

Only reading is implemented.

## Installation

```shell
pip install addressablestools
```

## Parse JSON catalogs

```python
from pathlib import Path

from addressablestools import parse_json
from addressablestools.models import AssetBundleRequestOptions, WrappedSerializedObject


data = Path("tests/samples/catalog.json").read_text(encoding="utf-8")
catalog = parse_json(data)

for key, locations in catalog.resources.items():
    if not isinstance(key, str) or not key.endswith(".bundle"):
        continue

    resource_data = locations[0].data
    if isinstance(resource_data, WrappedSerializedObject) and isinstance(
        resource_data.object,
        AssetBundleRequestOptions,
    ):
        print(
            f"Bundle {key}, Crc: {resource_data.object.crc}, "
            f"Hash: {resource_data.object.hash}"
        )
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
asset_location = catalog.resources[asset_key][0]

print(asset_location.primary_key)
print(asset_location.internal_id)
print(asset_location.provider_id)

if asset_location.dependency_key is not None:
    dependency_location = catalog.resources[asset_location.dependency_key][0]
    print(dependency_location.primary_key)
    print(dependency_location.internal_id)
```

## Custom binary object handling

Binary catalogs may contain custom serialized object types. Use a patcher to remap a custom match name to a supported built-in match name, or return `None` to delegate parsing to a handler.

```python
from pathlib import Path

from addressablestools import parse_binary
from addressablestools.decoder import SerializedObjectDecoder


def patcher(match_name: str) -> str | None:
    if match_name == "Custom.Assembly; Custom.AssetBundleRequestOptions":
        return SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME
    return match_name


catalog = parse_binary(Path("catalog.bin").read_bytes(), patcher=patcher)
```

You can also let a handler parse a custom object directly.

```python
from pathlib import Path

from addressablestools import parse_binary
from addressablestools.binary import CatalogBinaryReader


def patcher(match_name: str) -> str | None:
    if match_name == "Custom.Assembly; Custom.Int32Value":
        return None
    return match_name


def handler(reader: CatalogBinaryReader, offset: int, is_default: bool) -> object:
    if is_default:
        return 0
    reader.seek(offset)
    return reader.read_int32()


catalog = parse_binary(Path("catalog.bin").read_bytes(), patcher=patcher, handler=handler)
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
