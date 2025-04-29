# AddressablesToolsPy

Python copy of AddressablesTools

**Only reading is implemented**

### Usage

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
