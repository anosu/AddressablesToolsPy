# AddressablesToolsPy

Python library for reading Unity Addressables catalog files.

Only reading is implemented.

## Usage

```shell
pip install addressablestools
```

```python
from pathlib import Path

from addressablestools import parse
from addressablestools.models import AssetBundleRequestOptions, WrappedSerializedObject


data = Path("tests/samples/catalog.json").read_text(encoding="utf-8")
catalog = parse(data)

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

## Binary custom object parsing

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

The legacy API is implemented as a thin compatibility module over `addressablestools`. New code should import `addressablestools` directly.
