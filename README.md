# AddressablesToolsPy

Python copy of [AddressablesTools](https://github.com/nesrak1/AddressablesTools)

**Only reading is implemented**

### Usage

```shell
pip install addressablestools
```

```python
from pathlib import Path
from AddressablesTools import parse


def main():
    data = Path("tests/samples/catalog.json").read_text("utf-8")
    catalog = parse(data)
    for key, locs in catalog.Resources.items():
        if not isinstance(key, str):
            continue
        if not key.endswith(".bundle"):
            continue
        res_loc = locs[0]
        print(
            f"Bundle {key}, Crc: {res_loc.Data.Object.Crc}, Hash: {res_loc.Data.Object.Hash}"
        )

    print("-" * 50)

    asset_locs = catalog.Resources[
        "Assets/Paripari/AddressableAssets/VFX Texture Assets/ParticleTextures/sparkle.png"
    ]
    dep_key = asset_locs[0].DependencyKey
    print(f"Dependency of {asset_locs[0].PrimaryKey}: {dep_key}")
    dep_bundle = catalog.Resources[dep_key][0]
    print(f"ProviderId of {dep_bundle.PrimaryKey}: {dep_bundle.ProviderId}")
    print(f"InternalId of {dep_bundle.PrimaryKey}: {dep_bundle.InternalId}")


if __name__ == "__main__":
    main()
```

### Custom object parsing

**This is just used for binary reading.**

There may be some custom assemblies and classes uesd to load AssetBundles.

In gerneral, tool will not be able to parse these objects and raise an error.

For example, if you encounter an error like:
```
Unsupported object type: 0; System.String
```

You can provide a patcher and a handler (optional) to try to parse the custom object type.

#### Patcher and Handler

A patcher is a function that takes a `matchName: str` and returns a new matchName or `None` which is used to decide how the object should be parsed.

There is a default patcher that returns the original matchName.

A handler is a function that takes 3 arguments: `reader: CatalogBinaryReader`, `objectOffset: int`, and `isDefault: bool` and returns `Any` (the parsed object).

When the patcher returns `None`, your custom handler will be used.

Followings are some examples:

```python
from pathlib import Path
import AddressablesTools
from AddressablesTools.classes import SerializedObjectDecoder


def patcher(matchName: str) -> str:
    # just try to parse custom AssetBundleRequestOptions in default way
    if matchName == "GeePlus.GPUL.AddressablesManager; GeePlus.GPUL.AddressablesManager.ResourceProviders.EncryptedAssetBundleRequestOptions" # custom AssetBundleRequestOptions class
        return SerializedObjectDecoder.ABRO_MATCHNAME # default matchName for AssetBundleRequestOptions
    return matchName

data = Path("catalog.bin").read_bytes()

catalog = AddressablesTools.parse_binary(data, patcher=patcher)
```

```python
from typing import Any
from pathlib import Path
import AddressablesTools
from AddressablesTools.Reader.CatalogBinaryReader import CatalogBinaryReader


def patcher(matchName: str) -> str:
    if matchName == "Custom; System.Int32"
        return None
    return matchName

def handler(reader: CatalogBinaryReader, offset: int, is_default: bool) -> Any:
    if is_default:
        return 0
    reader.Seek(offset)
    return reader.ReadInt32()

data = Path("catalog.bin").read_bytes()

catalog = AddressablesTools.parse_binary(data, patcher=patcher, handler=handler)
```

> I havn't tested the above code, it may not work.